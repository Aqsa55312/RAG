import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.api.routes import router as api_router
from app.services.vector_db import get_vector_db_service

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("enterprise_rag")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown routines."""
    logger.info("=" * 70)
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} ({settings.APP_ENV})")
    logger.info(f"Ollama Target : {settings.OLLAMA_BASE_URL} (Model: {settings.OLLAMA_MODEL})")
    logger.info(f"Vector Store  : {settings.VECTOR_DB_TYPE} (Collection: {settings.CHROMA_COLLECTION_NAME})")
    logger.info(f"Auth Enabled  : {settings.AUTH_REQUIRED} (JWT HS256)")
    logger.info(f"CORS Allowed  : {settings.CORS_ORIGINS}")
    logger.info("=" * 70)

    # Initialize Vector DB on startup
    try:
        db = get_vector_db_service()
        count = db.count()
        logger.info(f"ChromaDB ready. Collection '{settings.CHROMA_COLLECTION_NAME}' vector count: {count}")
    except Exception as e:
        logger.warning(f"Vector DB startup initialization notice: {e}")

    yield

    logger.info(f"Shutting down {settings.APP_NAME}...")


app = FastAPI(
    title=settings.APP_NAME,
    description="Enterprise Knowledge Base Retrieval-Augmented Generation (RAG) backend engine with Ollama, ChromaDB, Confluence, Notion, and RBAC Security.",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Middleware using configured cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Register API Routers with prefix
app.include_router(api_router)

# Mount Static Files & Web UI Dashboard
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", tags=["General"])
async def root():
    """Serve interactive Web Dashboard UI."""
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "status": "online",
        "docs_url": "/docs",
        "health_url": f"{settings.API_PREFIX}/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
