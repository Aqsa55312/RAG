from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Auth & RBAC Schemas
# -----------------------------------------------------------------------------

class TokenRequest(BaseModel):
    """Schema to generate a JWT token for a specific RBAC role."""
    user_id: str = Field(default="user_001", description="ID Pengguna", example="emp_101")
    email: str = Field(default="user@company.com", description="Email Pengguna", example="alex@company.com")
    role: str = Field(
        default="employee",
        description="Role RBAC ('admin', 'engineering', 'employee')",
        example="engineering"
    )


class TokenResponse(BaseModel):
    """Schema returned after successful token creation/authentication."""
    access_token: str = Field(..., description="JWT Bearer Token")
    token_type: str = Field(default="Bearer", description="Tipe token")
    role: str = Field(..., description="Role RBAC")
    allowed_spaces: List[str] = Field(..., description="Daftar ruang data/spaces yang diizinkan untuk diakses")
    can_sync: bool = Field(..., description="Hak akses untuk melakukan ingestion/sync data")
    expires_in_seconds: int = Field(..., description="Masa berlaku token dalam detik")


class UserPayload(BaseModel):
    """Schema representing the authenticated user in request context."""
    user_id: str
    email: str
    role: str
    allowed_spaces: List[str]
    can_sync: bool


# -----------------------------------------------------------------------------
# RAG Query Schemas
# -----------------------------------------------------------------------------

class QueryRequest(BaseModel):
    """Schema for incoming RAG user questions."""
    query: str = Field(..., description="Pertanyaan dari pengguna", example="Bagaimana arsitektur microservices kita?")
    top_k: Optional[int] = Field(default=None, description="Jumlah potongan dokumen relevan yang diambil (default dari config)", example=4)
    filter_space: Optional[str] = Field(default=None, description="Filter ruang data/kategori tertentu (misal: 'ENG', 'HR', 'OPS', 'GENERAL')", example="ENG")
    filter_source: Optional[str] = Field(default=None, description="Filter sumber (misal: 'confluence', 'notion', 'manual')", example="confluence")


class SourceDocument(BaseModel):
    """Schema for source references in RAG response."""
    content: str = Field(..., description="Teks isi dokumen/chunk")
    source: str = Field(..., description="Sumber dokumen (confluence, notion, manual, dll.)")
    title: Optional[str] = Field(default="Untitled", description="Judul dokumen atau halaman")
    space: Optional[str] = Field(default="GENERAL", description="Space/Kategori dokumen (untuk RBAC)")
    url: Optional[str] = Field(default=None, description="Tautan langsung ke sumber")
    score: Optional[float] = Field(default=None, description="Cosine distance / similarity score")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata tambahan")


class QueryResponse(BaseModel):
    """Schema for final answer from RAG pipeline."""
    query: str = Field(..., description="Pertanyaan asli")
    answer: str = Field(..., description="Jawaban yang dihasilkan oleh LLM")
    sources: List[SourceDocument] = Field(default_factory=list, description="Kutipan sumber data yang dipakai")
    model: str = Field(..., description="Model Ollama yang digunakan")
    user_role: Optional[str] = Field(default=None, description="Role pengguna yang mengajukan query")
    applied_spaces: List[str] = Field(default_factory=list, description="Filter spaces yang diterapkan berdasarkan RBAC")


# -----------------------------------------------------------------------------
# Ingestion Schemas
# -----------------------------------------------------------------------------

class IngestConfluenceRequest(BaseModel):
    """Schema to trigger Confluence ingestion."""
    spaces: Optional[List[str]] = Field(default=None, description="Daftar Confluence Spaces (default: ['ENG', 'HR', 'OPS'])")
    page_ids: Optional[List[str]] = Field(default=None, description="Daftar Page IDs spesifik")
    url: Optional[str] = Field(default=None, description="Override Confluence Base URL")


class IngestNotionRequest(BaseModel):
    """Schema to trigger Notion ingestion."""
    database_ids: Optional[List[str]] = Field(default=None, description="Daftar Notion Database IDs to ingest")
    page_ids: Optional[List[str]] = Field(default=None, description="Daftar Page IDs spesifik")


class IngestRawTextRequest(BaseModel):
    """Schema to ingest raw text or custom documents."""
    title: str = Field(..., description="Judul dokumen", example="SOP Keamanan Sistem")
    content: str = Field(..., description="Isi teks dokumen", example="Semua karyawan wajib mengaktifkan 2FA.")
    space: str = Field(default="GENERAL", description="Space/Kategori untuk kontrol akses RBAC (misal: 'ENG', 'HR', 'OPS', 'GENERAL')", example="ENG")
    source: str = Field(default="manual", description="Label sumber dokumen", example="manual")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadata kustom")


class IngestResponse(BaseModel):
    """Schema for ingestion response."""
    status: str = Field(..., description="Status proses ingestion ('success', 'partial', 'failed')")
    source: str = Field(..., description="Sumber yang di-ingest")
    documents_processed: int = Field(..., description="Jumlah dokumen yang diproses")
    chunks_created: int = Field(..., description="Jumlah chunk yang dibuat dan disimpan ke Vector DB")
    message: str = Field(..., description="Pesan deskripsi hasil ingestion")


# -----------------------------------------------------------------------------
# Health & Status Schemas
# -----------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Schema for system health check."""
    status: str = Field(..., description="Status API keseluruhan")
    version: str = Field(..., description="Versi aplikasi")
    environment: str = Field(..., description="Environment runtime (development/production)")
    vector_db_status: str = Field(..., description="Status koneksi Vector DB")
    ollama_status: str = Field(..., description="Status koneksi Ollama")
    total_vectors: int = Field(..., description="Total vektor dalam collection")
    active_collection: str = Field(..., description="Nama collection ChromaDB yang aktif")
