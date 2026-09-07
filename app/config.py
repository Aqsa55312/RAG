import json
import os
from functools import lru_cache
from typing import List, Dict, Any, Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_json_config() -> Dict[str, Any]:
    """Load config.json if present in the workspace root."""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


_json_cfg = _load_json_config()
_proj_info = _json_cfg.get("project_info", {})
_server = _json_cfg.get("server", {})
_llm_prov = _json_cfg.get("llm_provider", {})
_gen_model = _llm_prov.get("models", {}).get("generation", {})
_emb_model = _llm_prov.get("models", {}).get("embedding", {})
_vstore = _json_cfg.get("vector_store", {})
_ingest_pipe = _json_cfg.get("ingestion_pipeline", {})
_chunking = _ingest_pipe.get("chunking", {})
_conns = _ingest_pipe.get("connectors", {})
_conf_conn = _conns.get("confluence", {})
_notion_conn = _conns.get("notion", {})
_rag_set = _json_cfg.get("rag_settings", {})
_retrieval = _rag_set.get("retrieval", {})
_rerank = _retrieval.get("reranking", {})
_prompts = _rag_set.get("prompts", {})
_sec = _json_cfg.get("security_and_access", {})


class Settings(BaseSettings):
    """Application Configuration matching the Enterprise Architecture specification."""

    # Project Info
    APP_NAME: str = _proj_info.get("name", "Enterprise Knowledge Base RAG")
    APP_VERSION: str = _proj_info.get("version", "1.0.0")
    APP_ENV: str = _proj_info.get("environment", "development")

    # Server Settings
    HOST: str = _server.get("host", "0.0.0.0")
    PORT: int = _server.get("port", 8000)
    DEBUG: bool = _server.get("debug", True)
    API_PREFIX: str = _server.get("api_prefix", "/api/v1")
    CORS_ORIGINS: Union[List[str], str] = _server.get("cors_origins", [
        "http://localhost:3000",
        "https://internal.company.com"
    ])

    # LLM Provider (Ollama)
    LLM_PROVIDER: str = _llm_prov.get("provider", "ollama")
    OLLAMA_BASE_URL: str = _llm_prov.get("base_url", "http://localhost:11434")
    OLLAMA_MODEL: str = _gen_model.get("name", "llama3")
    OLLAMA_TEMPERATURE: float = _gen_model.get("temperature", 0.2)
    OLLAMA_TOP_P: float = _gen_model.get("top_p", 0.9)
    OLLAMA_MAX_TOKENS: int = _gen_model.get("max_tokens", 2048)
    OLLAMA_CONTEXT_WINDOW: int = _gen_model.get("context_window", 8192)

    # Embedding Model
    OLLAMA_EMBED_MODEL: str = _emb_model.get("name", "nomic-embed-text")
    EMBEDDING_DIMENSION: int = _emb_model.get("dimension", 768)

    # Vector Store (ChromaDB)
    VECTOR_DB_TYPE: str = _vstore.get("provider", "chromadb")
    CHROMA_PERSIST_DIRECTORY: str = _vstore.get("persist_directory", "./data/chroma_db")
    CHROMA_COLLECTION_NAME: str = _vstore.get("collection_name", "enterprise_knowledge")
    DISTANCE_METRIC: str = _vstore.get("distance_metric", "cosine")

    # Ingestion Pipeline & Chunking
    CHUNK_SIZE: int = _chunking.get("chunk_size", 1000)
    CHUNK_OVERLAP: int = _chunking.get("chunk_overlap", 150)
    CHUNK_SEPARATORS: Union[List[str], str] = _chunking.get("separators", ["\n\n", "\n", " ", ""])

    # Confluence Connector
    CONFLUENCE_ENABLED: bool = _conf_conn.get("enabled", True)
    CONFLUENCE_URL: Optional[str] = _conf_conn.get("base_url", "https://your-domain.atlassian.net")
    CONFLUENCE_USERNAME: Optional[str] = None
    CONFLUENCE_API_TOKEN: Optional[str] = None
    CONFLUENCE_DEFAULT_SPACES: Union[List[str], str] = _conf_conn.get("default_spaces", ["ENG", "HR", "OPS"])
    CONFLUENCE_SYNC_INTERVAL_HOURS: int = _conf_conn.get("sync_interval_hours", 24)

    # Notion Connector
    NOTION_ENABLED: bool = _notion_conn.get("enabled", True)
    NOTION_API_KEY: Optional[str] = None
    NOTION_DATABASE_IDS: Union[List[str], str] = _notion_conn.get("database_ids", [
        "database_id_sop_internal",
        "database_id_tech_docs"
    ])

    # RAG Settings & Retrieval
    TOP_K_RESULTS: int = _retrieval.get("top_k", 4)
    SEARCH_TYPE: str = _retrieval.get("search_type", "hybrid")
    RERANKING_ENABLED: bool = _rerank.get("enabled", False)
    RERANKING_MODEL: str = _rerank.get("model", "bge-reranker-large")

    SYSTEM_PROMPT: str = _prompts.get(
        "system_prompt",
        "Anda adalah Asisten AI Internal Perusahaan. Jawab pertanyaan hanya berdasarkan konteks yang diberikan di bawah ini. Jika jawaban tidak ditemukan di dalam konteks, katakan secara jujur bahwa Anda tidak tahu. Jangan mengarang informasi."
    )
    RAG_TEMPLATE: str = _prompts.get(
        "rag_template",
        "Konteks Dokumen:\n{context}\n\nPertanyaan User: {question}\n\nJawaban Sesuai Konteks (sertakan referensi sumber):"
    )

    # Security and Access (JWT & RBAC)
    AUTH_REQUIRED: bool = _sec.get("auth_required", True)
    JWT_SECRET_KEY: str = "super-secret-enterprise-rag-jwt-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 1440
    RBAC_ROLES: Dict[str, Any] = _sec.get("rbac_roles", {
        "admin": {
            "allowed_spaces": ["*"],
            "can_sync": True
        },
        "engineering": {
            "allowed_spaces": ["ENG", "OPS", "GENERAL"],
            "can_sync": False
        },
        "employee": {
            "allowed_spaces": ["HR", "GENERAL"],
            "can_sync": False
        }
    })

    @field_validator("CONFLUENCE_DEFAULT_SPACES", "NOTION_DATABASE_IDS", "CORS_ORIGINS", "CHUNK_SEPARATORS", mode="after")
    @classmethod
    def parse_str_list(cls, v):
        if isinstance(v, str):
            v_str = v.strip()
            if v_str.startswith("[") and v_str.endswith("]"):
                try:
                    return json.loads(v_str)
                except Exception:
                    pass
            return [item.strip() for item in v_str.split(",") if item.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached singleton Settings instance."""
    return Settings()
