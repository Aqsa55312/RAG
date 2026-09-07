import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from app.config import Settings, get_settings
from app.api.auth import (
    create_access_token,
    get_current_user,
    require_sync_permission,
)
from app.models.schemas import (
    TokenRequest,
    TokenResponse,
    UserPayload,
    QueryRequest,
    QueryResponse,
    IngestConfluenceRequest,
    IngestNotionRequest,
    IngestRawTextRequest,
    IngestResponse,
    HealthResponse,
)
from app.services.rag import RAGService, get_rag_service
from app.services.ingestion import IngestionService, get_ingestion_service
from app.services.vector_db import VectorDBService, get_vector_db_service
from app.services.confluence import ConfluenceService, get_confluence_service
from app.services.notion import NotionService, get_notion_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Enterprise RAG"])


# -----------------------------------------------------------------------------
# Authentication & Token Generation
# -----------------------------------------------------------------------------

@router.post(
    "/auth/token",
    response_model=TokenResponse,
    tags=["Authentication & RBAC"],
    summary="Generate JWT Token for Role",
    description="Menghasilkan token JWT Bearer berdasarkan role pengguna ('admin', 'engineering', 'employee')."
)
async def generate_token(
    request: TokenRequest,
    settings: Settings = Depends(get_settings)
):
    role = request.role.lower()
    if role not in settings.RBAC_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{request.role}' tidak valid. Role yang tersedia: {list(settings.RBAC_ROLES.keys())}"
        )

    token = create_access_token(
        user_id=request.user_id,
        email=request.email,
        role=role,
        settings=settings
    )
    role_info = settings.RBAC_ROLES[role]

    return TokenResponse(
        access_token=token,
        token_type="Bearer",
        role=role,
        allowed_spaces=role_info.get("allowed_spaces", ["*"]),
        can_sync=role_info.get("can_sync", False),
        expires_in_seconds=settings.JWT_EXPIRATION_MINUTES * 60
    )


# -----------------------------------------------------------------------------
# RAG Query Endpoint
# -----------------------------------------------------------------------------

@router.post(
    "/rag/query",
    response_model=QueryResponse,
    summary="Ask Question to RAG Pipeline (RBAC Protected)",
    description="Mengajukan pertanyaan ke sistem RAG dengan filter akses data otomatis berdasarkan role JWT pengguna."
)
async def query_rag(
    request: QueryRequest,
    current_user: UserPayload = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service)
):
    try:
        response = rag_service.query(
            question=request.query,
            top_k=request.top_k,
            allowed_spaces=current_user.allowed_spaces,
            filter_space=request.filter_space,
            filter_source=request.filter_source,
            user_role=current_user.role
        )
        return response
    except Exception as e:
        logger.error(f"Error during RAG query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal memproses pertanyaan RAG: {str(e)}"
        )


# -----------------------------------------------------------------------------
# Ingestion Endpoints (Requires can_sync / Admin)
# -----------------------------------------------------------------------------

@router.post(
    "/ingest/text",
    response_model=IngestResponse,
    summary="Ingest Custom Raw Text (Admin Only)",
    description="Menambahkan dokumen teks manual dengan penandaan space untuk kontrol akses RBAC."
)
async def ingest_raw_text(
    request: IngestRawTextRequest,
    current_user: UserPayload = Depends(require_sync_permission),
    ingestion_service: IngestionService = Depends(get_ingestion_service)
):
    try:
        raw_doc = [{
            "title": request.title,
            "content": request.content,
            "space": request.space or "GENERAL",
            "source": request.source or "manual",
            "metadata": request.metadata or {}
        }]
        
        result = ingestion_service.ingest_documents(raw_doc)
        
        return IngestResponse(
            status="success",
            source=request.source or "manual",
            documents_processed=result["documents_processed"],
            chunks_created=result["chunks_created"],
            message=f"Berhasil mengindeks {result['chunks_created']} potongan dokumen ke Space '{request.space}'."
        )
    except Exception as e:
        logger.error(f"Error during raw text ingestion: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal melakukan ingestion teks: {str(e)}"
        )


@router.post(
    "/ingest/confluence",
    response_model=IngestResponse,
    summary="Ingest Data from Confluence (Admin Only)",
    description="Sinkronisasi halaman dari Confluence untuk default spaces (ENG, HR, OPS) atau custom spaces."
)
async def ingest_confluence(
    request: IngestConfluenceRequest,
    current_user: UserPayload = Depends(require_sync_permission),
    confluence_service: ConfluenceService = Depends(get_confluence_service),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    settings: Settings = Depends(get_settings)
):
    try:
        documents = []
        target_spaces = request.spaces or settings.CONFLUENCE_DEFAULT_SPACES

        if request.page_ids:
            for page_id in request.page_ids:
                doc = confluence_service.fetch_page_by_id(page_id)
                if doc.get("content"):
                    documents.append(doc)
        elif target_spaces:
            for space in target_spaces:
                docs = confluence_service.fetch_space_pages(space)
                documents.extend(docs)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tidak ada Confluence Space yang ditentukan untuk sinkronisasi."
            )

        if not documents:
            return IngestResponse(
                status="partial",
                source="confluence",
                documents_processed=0,
                chunks_created=0,
                message="Tidak ada halaman Confluence yang berhasil diambil atau kredensial belum dikonfigurasi."
            )

        result = ingestion_service.ingest_documents(documents)

        return IngestResponse(
            status="success",
            source="confluence",
            documents_processed=result["documents_processed"],
            chunks_created=result["chunks_created"],
            message=f"Berhasil mengindeks {result['documents_processed']} halaman Confluence ({result['chunks_created']} chunks)."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during Confluence ingestion: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal melakukan ingestion Confluence: {str(e)}"
        )


@router.post(
    "/ingest/notion",
    response_model=IngestResponse,
    summary="Ingest Data from Notion (Admin Only)",
    description="Sinkronisasi halaman dari database Notion default atau database kustom."
)
async def ingest_notion(
    request: IngestNotionRequest,
    current_user: UserPayload = Depends(require_sync_permission),
    notion_service: NotionService = Depends(get_notion_service),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    settings: Settings = Depends(get_settings)
):
    try:
        documents = []
        target_dbs = request.database_ids or settings.NOTION_DATABASE_IDS

        if request.page_ids:
            for page_id in request.page_ids:
                doc = notion_service.fetch_page_by_id(page_id)
                if doc.get("content"):
                    documents.append(doc)
        elif target_dbs:
            for db_id in target_dbs:
                docs = notion_service.fetch_database_pages(db_id)
                documents.extend(docs)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tidak ada Notion Database ID yang ditentukan untuk sinkronisasi."
            )

        if not documents:
            return IngestResponse(
                status="partial",
                source="notion",
                documents_processed=0,
                chunks_created=0,
                message="Tidak ada halaman Notion yang berhasil diambil atau kredensial belum dikonfigurasi."
            )

        result = ingestion_service.ingest_documents(documents)

        return IngestResponse(
            status="success",
            source="notion",
            documents_processed=result["documents_processed"],
            chunks_created=result["chunks_created"],
            message=f"Berhasil mengindeks {result['documents_processed']} halaman Notion ({result['chunks_created']} chunks)."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during Notion ingestion: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal melakukan ingestion Notion: {str(e)}"
        )


# -----------------------------------------------------------------------------
# Health Check Endpoint
# -----------------------------------------------------------------------------

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check System Health",
    description="Mengecek status kesehatan API, koneksi Vector Database, dan koneksi Ollama LLM."
)
async def health_check(
    settings: Settings = Depends(get_settings),
    vector_db: VectorDBService = Depends(get_vector_db_service),
    rag_service: RAGService = Depends(get_rag_service)
):
    vdb_ok = vector_db.check_health()
    ollama_ok = rag_service.check_ollama_health()
    total_vectors = vector_db.count()

    overall_status = "healthy" if (vdb_ok and ollama_ok) else "degraded"

    return HealthResponse(
        status=overall_status,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        vector_db_status="connected" if vdb_ok else "disconnected",
        ollama_status="connected" if ollama_ok else "unreachable",
        total_vectors=total_vectors,
        active_collection=settings.CHROMA_COLLECTION_NAME
    )
