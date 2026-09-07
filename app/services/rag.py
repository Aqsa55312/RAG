import logging
from typing import List, Dict, Any, Optional
import httpx
from app.config import get_settings
from app.services.vector_db import VectorDBService, get_vector_db_service
from app.models.schemas import QueryResponse, SourceDocument

logger = logging.getLogger(__name__)


class RAGService:
    """Service to orchestrate retrieval from ChromaDB and generation via Ollama LLM with RBAC."""

    def __init__(self, vector_db: Optional[VectorDBService] = None):
        self.settings = get_settings()
        self.vector_db = vector_db or get_vector_db_service()

    def _get_query_embedding(self, query: str) -> Optional[List[float]]:
        """Get embedding for user query from Ollama embedding model."""
        url = f"{self.settings.OLLAMA_BASE_URL.rstrip('/')}/api/embeddings"
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    url,
                    json={
                        "model": self.settings.OLLAMA_EMBED_MODEL,
                        "prompt": query
                    }
                )
                if resp.status_code == 200:
                    return resp.json().get("embedding")
        except Exception as e:
            logger.warning(f"Failed to generate query embedding via Ollama: {e}. Using Chroma search.")
        return None

    def _build_context(self, search_results: List[Dict[str, Any]]) -> str:
        """Format retrieved search results into readable context block."""
        if not search_results:
            return "Tidak ada dokumen relevan yang ditemukan dalam basis pengetahuan yang diizinkan."

        context_parts = []
        for idx, item in enumerate(search_results, 1):
            meta = item.get("metadata", {})
            title = meta.get("title", "Dokumen")
            space = meta.get("space", "GENERAL")
            source = meta.get("source", "unknown")
            content = item.get("content", "").strip()
            context_parts.append(
                f"[Dokumen #{idx}] (Sumber: {source} | Space: {space} | Judul: {title})\n{content}"
            )

        return "\n\n---\n\n".join(context_parts)

    def _call_ollama_llm(self, full_prompt: str) -> str:
        """Call Ollama /api/generate with custom parameters (temperature, top_p, num_predict, num_ctx)."""
        url = f"{self.settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate"
        payload = {
            "model": self.settings.OLLAMA_MODEL,
            "prompt": full_prompt,
            "system": self.settings.SYSTEM_PROMPT,
            "stream": False,
            "options": {
                "temperature": self.settings.OLLAMA_TEMPERATURE,
                "top_p": self.settings.OLLAMA_TOP_P,
                "num_predict": self.settings.OLLAMA_MAX_TOKENS,
                "num_ctx": self.settings.OLLAMA_CONTEXT_WINDOW
            }
        }

        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(url, json=payload)
                if resp.status_code == 200:
                    return resp.json().get("response", "").strip()
                else:
                    error_msg = f"Ollama returned error status {resp.status_code}: {resp.text}"
                    logger.error(error_msg)
                    return f"Error: Tidak dapat menghasilkan jawaban dari LLM ({resp.status_code})."
        except httpx.ConnectError:
            msg = (
                f"Tidak dapat terhubung ke Ollama di {self.settings.OLLAMA_BASE_URL}. "
                "Pastikan Ollama aktif dan model terpasang."
            )
            logger.error(msg)
            return msg
        except Exception as e:
            logger.error(f"Error communicating with Ollama: {e}", exc_info=True)
            return f"Terjadi kesalahan saat memproses jawaban: {str(e)}"

    def query(
        self,
        question: str,
        top_k: Optional[int] = None,
        allowed_spaces: Optional[List[str]] = None,
        filter_space: Optional[str] = None,
        filter_source: Optional[str] = None,
        user_role: Optional[str] = "employee"
    ) -> QueryResponse:
        """Execute full RAG pipeline: RBAC Retrieval -> Augment Template -> Ollama Generation."""
        k = top_k or self.settings.TOP_K_RESULTS
        spaces = allowed_spaces or ["*"]

        # 1. Retrieve relevant chunks with RBAC constraint
        query_embed = self._get_query_embedding(question)
        search_results = self.vector_db.search(
            query_text=question if query_embed is None else None,
            query_embedding=query_embed,
            top_k=k,
            allowed_spaces=spaces,
            filter_space=filter_space,
            filter_source=filter_source
        )

        # 2. Build Augmented Prompt using configured RAG_TEMPLATE
        context_text = self._build_context(search_results)
        
        # Inject into configured rag_template
        try:
            formatted_prompt = self.settings.RAG_TEMPLATE.format(
                context=context_text,
                question=question
            )
        except Exception:
            formatted_prompt = f"Konteks Dokumen:\n{context_text}\n\nPertanyaan User: {question}\n\nJawaban Sesuai Konteks:"

        # 3. Generate Answer from Ollama
        llm_answer = self._call_ollama_llm(formatted_prompt)

        # 4. Format Sources
        sources: List[SourceDocument] = []
        for res in search_results:
            meta = res.get("metadata", {})
            sources.append(
                SourceDocument(
                    content=res.get("content", ""),
                    source=meta.get("source", "unknown"),
                    title=meta.get("title", "Untitled"),
                    space=meta.get("space", "GENERAL"),
                    url=meta.get("url"),
                    score=res.get("score"),
                    metadata=meta
                )
            )

        return QueryResponse(
            query=question,
            answer=llm_answer,
            sources=sources,
            model=self.settings.OLLAMA_MODEL,
            user_role=user_role,
            applied_spaces=spaces
        )

    def check_ollama_health(self) -> bool:
        """Check if Ollama server is up and reachable."""
        url = f"{self.settings.OLLAMA_BASE_URL.rstrip('/')}/api/version"
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url)
                return resp.status_code == 200
        except Exception:
            return False


def get_rag_service() -> RAGService:
    """Dependency injector for RAGService."""
    return RAGService()
