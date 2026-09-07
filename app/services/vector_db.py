import logging
import os
from typing import List, Dict, Any, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMADB_AVAILABLE = True
except ImportError:
    chromadb = None
    ChromaSettings = None
    CHROMADB_AVAILABLE = False


class VectorDBService:
    """Connector and interface for ChromaDB vector store with cosine distance and RBAC space filtering."""

    def __init__(self):
        self.settings = get_settings()
        self._client = None
        self._collection = None
        self._init_db()

    def _init_db(self):
        """Initialize ChromaDB persistent client and collection."""
        if not CHROMADB_AVAILABLE:
            logger.warning(
                "ChromaDB is not installed. Please install it using 'pip install chromadb' "
                "or 'pip install -r requirements.txt'."
            )
            return

        try:
            os.makedirs(self.settings.CHROMA_PERSIST_DIRECTORY, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=self.settings.CHROMA_PERSIST_DIRECTORY,
                settings=ChromaSettings(anonymized_telemetry=False)
            )

            
            # Map distance metric
            metric = self.settings.DISTANCE_METRIC.lower()
            if metric not in ["cosine", "l2", "ip"]:
                metric = "cosine"

            self._collection = self._client.get_or_create_collection(
                name=self.settings.CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": metric}
            )
            logger.info(
                f"ChromaDB initialized at '{self.settings.CHROMA_PERSIST_DIRECTORY}', "
                f"collection: '{self.settings.CHROMA_COLLECTION_NAME}' (metric: {metric}, count: {self._collection.count()})"
            )
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}", exc_info=True)
            raise e

    def add_documents(
        self,
        texts: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
        embeddings: Optional[List[List[float]]] = None,
    ) -> int:
        """Add text documents, metadata, and optional embeddings to the collection."""
        if not texts:
            return 0

        if self._collection is None:
            raise RuntimeError(
                "ChromaDB collection is not initialized. Make sure 'chromadb' is installed."
            )

        # Sanitize metadata values for ChromaDB
        sanitized_metadatas = []
        for meta in metadatas:
            sanitized = {}
            for k, v in meta.items():
                if isinstance(v, (str, int, float, bool)):
                    sanitized[k] = v
                elif v is None:
                    sanitized[k] = ""
                else:
                    sanitized[k] = str(v)
            # Ensure 'space' is always present for RBAC
            if "space" not in sanitized or not sanitized["space"]:
                sanitized["space"] = "GENERAL"
            sanitized_metadatas.append(sanitized)

        kwargs: Dict[str, Any] = {
            "documents": texts,
            "metadatas": sanitized_metadatas,
            "ids": ids,
        }
        if embeddings:
            kwargs["embeddings"] = embeddings

        self._collection.upsert(**kwargs)
        logger.info(f"Upserted {len(texts)} document chunks into ChromaDB '{self.settings.CHROMA_COLLECTION_NAME}'.")
        return len(texts)

    def _build_where_filter(
        self,
        allowed_spaces: Optional[List[str]] = None,
        filter_space: Optional[str] = None,
        filter_source: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Construct ChromaDB where filter combining RBAC allowed_spaces and user query filters."""
        conditions = []

        # 1. Space Filter & RBAC
        if allowed_spaces and "*" not in allowed_spaces:
            if filter_space:
                # User asked for specific space: check if it's within allowed_spaces
                if filter_space in allowed_spaces:
                    conditions.append({"space": {"$eq": filter_space}})
                else:
                    # Requesting space not permitted: force match to impossible
                    conditions.append({"space": {"$eq": "__FORBIDDEN__"}})
            else:
                # Restrict to all allowed spaces
                if len(allowed_spaces) == 1:
                    conditions.append({"space": {"$eq": allowed_spaces[0]}})
                else:
                    conditions.append({"space": {"$in": allowed_spaces}})
        elif filter_space:
            # User is admin (*) and requested specific space
            conditions.append({"space": {"$eq": filter_space}})

        # 2. Source Filter
        if filter_source:
            conditions.append({"source": {"$eq": filter_source}})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def search(
        self,
        query_text: Optional[str] = None,
        query_embedding: Optional[List[float]] = None,
        top_k: int = 4,
        allowed_spaces: Optional[List[str]] = None,
        filter_space: Optional[str] = None,
        filter_source: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search vector database by text or query embedding with RBAC filters."""
        if self._collection is None or self._collection.count() == 0:
            return []

        # Cap top_k to actual items in collection to prevent Chroma warning
        actual_k = min(top_k, self._collection.count())
        if actual_k <= 0:
            return []

        kwargs: Dict[str, Any] = {
            "n_results": actual_k,
        }

        if query_embedding is not None:
            kwargs["query_embeddings"] = [query_embedding]
        elif query_text is not None:
            kwargs["query_texts"] = [query_text]
        else:
            raise ValueError("Either query_text or query_embedding must be provided.")

        where_filter = self._build_where_filter(allowed_spaces, filter_space, filter_source)
        if where_filter:
            kwargs["where"] = where_filter

        try:
            results = self._collection.query(**kwargs)
        except Exception as e:
            logger.warning(f"ChromaDB query with filter {where_filter} failed ({e}). Falling back without filter.")
            kwargs.pop("where", None)
            results = self._collection.query(**kwargs)

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0] if results.get("distances") else [0.0] * len(documents)
        ids = results.get("ids", [[]])[0]

        formatted_results = []
        for doc_id, text, meta, dist in zip(ids, documents, metadatas, distances):
            formatted_results.append({
                "id": doc_id,
                "content": text,
                "metadata": meta,
                "score": float(dist),
            })

        return formatted_results

    def count(self) -> int:
        """Return total number of vectors in collection."""
        if self._collection is not None:
            return self._collection.count()
        return 0

    def check_health(self) -> bool:
        """Check if ChromaDB client is accessible."""
        try:
            return self._client.heartbeat() is not None
        except Exception:
            return False


_vector_db_instance: Optional[VectorDBService] = None


def get_vector_db_service() -> VectorDBService:
    """Dependency injector for VectorDBService singleton."""
    global _vector_db_instance
    if _vector_db_instance is None:
        _vector_db_instance = VectorDBService()
    return _vector_db_instance
