import logging
import uuid
from typing import List, Dict, Any, Optional
import httpx
from app.config import get_settings
from app.services.vector_db import VectorDBService, get_vector_db_service

logger = logging.getLogger(__name__)


class IngestionService:
    """Pipeline for document chunking, embedding generation, and vector indexing with RBAC metadata."""

    def __init__(self, vector_db: Optional[VectorDBService] = None):
        self.settings = get_settings()
        self.vector_db = vector_db or get_vector_db_service()

    def _split_text(
        self,
        text: str,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        separators: Optional[List[str]] = None
    ) -> List[str]:
        """Split text into manageable overlapping chunks using configured separators."""
        c_size = chunk_size or self.settings.CHUNK_SIZE
        c_overlap = chunk_overlap or self.settings.CHUNK_OVERLAP
        seps = separators or self.settings.CHUNK_SEPARATORS

        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=c_size,
                chunk_overlap=c_overlap,
                length_function=len,
                separators=seps
            )
            return splitter.split_text(text)
        except ImportError:
            chunks = []
            start = 0
            while start < len(text):
                end = start + c_size
                chunks.append(text[start:end])
                start += c_size - c_overlap
            return [c for c in chunks if c.strip()]

    def _generate_ollama_embeddings(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Generate vector embeddings for texts using Ollama Embedding API."""
        url = f"{self.settings.OLLAMA_BASE_URL.rstrip('/')}/api/embeddings"
        embeddings = []

        try:
            with httpx.Client(timeout=60.0) as client:
                for text in texts:
                    payload = {
                        "model": self.settings.OLLAMA_EMBED_MODEL,
                        "prompt": text
                    }
                    resp = client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        embeddings.append(data.get("embedding", []))
                    else:
                        logger.warning(
                            f"Ollama embedding request failed with status {resp.status_code}: {resp.text}. "
                            f"ChromaDB default embeddings will be used instead."
                        )
                        return None
            return embeddings
        except Exception as e:
            logger.warning(f"Could not connect to Ollama Embeddings API ({e}). Falling back to ChromaDB default embeddings.")
            return None

    def ingest_documents(self, raw_documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process and ingest a list of raw documents into the vector store.
        Each raw document must include:
          - title (str)
          - content (str)
          - space (str, e.g. 'ENG', 'HR', 'OPS', 'GENERAL')
          - source (str, e.g. 'confluence', 'notion', 'manual')
          - url (optional str)
          - metadata (optional dict)
        """
        if not raw_documents:
            return {"documents_processed": 0, "chunks_created": 0}

        all_chunks: List[str] = []
        all_metadatas: List[Dict[str, Any]] = []
        all_ids: List[str] = []

        for doc_idx, doc in enumerate(raw_documents):
            content = doc.get("content", "").strip()
            if not content:
                continue

            title = doc.get("title", f"Document_{doc_idx}")
            space = doc.get("space") or doc.get("metadata", {}).get("space", "GENERAL")
            source = doc.get("source", "manual")
            url = doc.get("url", "")
            base_meta = doc.get("metadata", {})

            chunks = self._split_text(content)

            for chunk_idx, chunk in enumerate(chunks):
                chunk_id = f"{source}_{space}_{uuid.uuid4().hex[:10]}"
                chunk_meta = {
                    **base_meta,
                    "title": title,
                    "space": space,
                    "source": source,
                    "url": url,
                    "chunk_index": chunk_idx,
                    "total_chunks": len(chunks)
                }

                all_chunks.append(chunk)
                all_metadatas.append(chunk_meta)
                all_ids.append(chunk_id)

        if not all_chunks:
            return {"documents_processed": len(raw_documents), "chunks_created": 0}

        # Embeddings via Ollama
        embeddings = self._generate_ollama_embeddings(all_chunks)

        # Store in vector database
        chunks_count = self.vector_db.add_documents(
            texts=all_chunks,
            metadatas=all_metadatas,
            ids=all_ids,
            embeddings=embeddings
        )

        return {
            "documents_processed": len(raw_documents),
            "chunks_created": chunks_count
        }


def get_ingestion_service() -> IngestionService:
    """Dependency injector for IngestionService."""
    return IngestionService()
