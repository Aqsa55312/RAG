# 🚀 Enterprise Knowledge Base AI (RAG System)

> **Enterprise Retrieval-Augmented Generation (RAG)** platform berbasis **FastAPI**, **Ollama** (LLM & Embeddings), **ChromaDB**, **Confluence & Notion Connectors**, sistem keamanan **Role-Based Access Control (RBAC & JWT)**, serta antarmuka web interaktif (**Glassmorphism Web Dashboard**).

---

## 🌟 Fitur Utama

- 💬 **Interactive AI Chat Assistant:** Antarmuka tanya-jawab cerdas dengan kutipan sumber (*citations*), skor relevansi cosine, dan rendering markdown.
- 👑 **1-Click RBAC Role Switcher:** Beralih peran instan (`Admin`, `Engineering`, `Employee`) langsung dari antarmuka Web UI tanpa perlu mengelola token manual.
- 🛡️ **Role-Based Space Filtering:** Pengambilan dokumen dibatasi secara otomatis berdasarkan ruang lingkup izin role:
  - **`Admin`**: Akses semua ruang data (`*`) + Izin Ingest Dokumen (`can_sync: true`).
  - **`Engineering`**: Akses ruang data `ENG`, `OPS`, dan `GENERAL`.
  - **`Employee`**: Akses ruang data `HR` dan `GENERAL`.
- 📥 **Knowledge Ingestion Hub:** Form input dokumen manual + konektor sinkronisasi untuk **Atlassian Confluence** dan **Notion Workspace**.
- ⚡ **Local LLM Engine:** Ditenagai oleh model lokal Ollama (`llama3` & `nomic-embed-text`) untuk menjaga privasi data perusahaan.
- 📊 **Live Health & Vector Explorer:** Pemantauan status koneksi server, total chunk tersimpan, dan inspektur JWT token secara real-time.

---

## 📁 Struktur Direktori

```
enterprise-rag/
├── config.json              # Konfigurasi Arsitektur Resmi Proyek
├── app/
│   ├── __init__.py          # Package Initialization & Versi
│   ├── config.py            # Pydantic Settings (Load config.json & .env)
│   ├── main.py              # Entry Point FastAPI, Static Files, & Lifespan
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py          # Modul JWT Auth & RBAC Dependencies
│   │   └── routes.py        # Endpoint RAG Query, Ingestion, & Auth
│   ├── services/
│   │   ├── __init__.py
│   │   ├── confluence.py    # Integrasi API Confluence & HTML Parser
│   │   ├── notion.py        # Integrasi API Notion & Block Parser
│   │   ├── ingestion.py     # Pipeline Chunking, Ollama Embeddings, & Space Tagging
│   │   ├── vector_db.py     # Konektor ChromaDB & Cosine Distance Filtering
│   │   └── rag.py           # Logika Retrieval, Augmentasi Prompt, & Ollama LLM
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py       # Skema Pydantic untuk Request, Response, & Auth
│   └── static/              # Antarmuka Web Dashboard
│       ├── index.html       # Single Page Application
│       ├── css/
│       │   └── style.css    # Desain Glassmorphism Dark Theme
│       └── js/
│           └── app.js       # Logika Frontend, State Management, & API Client
├── data/
│   └── chroma_db/           # Direktori Penyimpanan Lokal ChromaDB (.gitkeep)
├── docker-compose.yml       # Orkestrasi Docker (Ollama, Qdrant, & API)
├── Dockerfile               # Container Build Image
├── requirements.txt         # Daftar Dependensi Python
├── .env.example             # Template Environment Variables
├── .env                     # Konfigurasi Lokal
├── .gitignore               # Aturan Ignore Git
└── README.md                # Dokumentasi Lengkap Proyek
```

---

## 📋 Matriks Hak Akses (RBAC Matrix)

| Role | Allowed Spaces | Izin Ingest (`can_sync`) | Deskripsi |
|---|---|:---:|---|
| **`Admin`** | `*` (Semua Space) | ✅ **Ya** | Akses penuh ke seluruh dokumen dan diizinkan menambah/sinkronisasi data. |
| **`Engineering`** | `ENG`, `OPS`, `GENERAL` | ❌ Tidak | Akses terbatas pada dokumen arsitektur teknis, SOP server, dan info umum. |
| **`Employee`** | `HR`, `GENERAL` | ❌ Tidak | Akses terbatas pada kebijakan SDM/cuti dan informasi umum perusahaan. |

---

## 🚀 Panduan Memulai (Quick Start)

### 1. Prasyarat Sistem
- **Python:** Versi `3.10` atau lebih baru.
- **Ollama:** [Unduh Ollama](https://ollama.com/) dan pastikan model telah di-pull:
  ```bash
  ollama pull llama3
  ollama pull nomic-embed-text
  ```

---

### 2. Instalasi Dependensi

Gunakan Virtual Environment untuk menghindari konflik dependensi:

```powershell
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

---

### 3. Konfigurasi Lingkungan (`.env`)

Salin file template `.env.example` ke `.env`:
```bash
cp .env.example .env
```

Contoh konfigurasi standar pada file `.env`:
```ini
# Keamanan & JWT
AUTH_REQUIRED=true
JWT_SECRET_KEY="super-secret-enterprise-rag-jwt-key-change-in-production"

# Ollama LLM & Embeddings
OLLAMA_BASE_URL="http://localhost:11434"
OLLAMA_MODEL="llama3"
OLLAMA_EMBED_MODEL="nomic-embed-text"

# Vector Store (ChromaDB)
CHROMA_PERSIST_DIRECTORY="./data/chroma_db"
CHROMA_COLLECTION_NAME="enterprise_knowledge"
DISTANCE_METRIC="cosine"

# Confluence (Opsional)
CONFLUENCE_ENABLED=true
CONFLUENCE_URL="https://your-domain.atlassian.net"
CONFLUENCE_USERNAME="your-email@company.com"
CONFLUENCE_API_TOKEN="your-token"
CONFLUENCE_DEFAULT_SPACES="ENG,HR,OPS"

# Notion (Opsional)
NOTION_ENABLED=true
NOTION_API_KEY="secret_your_notion_key"
NOTION_DATABASE_IDS="database_id_sop_internal,database_id_tech_docs"
```

---

### 4. Menjalankan Aplikasi

#### Opsi A: Menggunakan Uvicorn (Lokal)
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Opsi B: Menggunakan Docker Compose
```bash
docker-compose up -d --build
```

---

## 🌐 Akses Antarmuka Web & Dokumentasi

- 🖥️ **Web Dashboard Interaktif:** Buka browser di 👉 **[http://localhost:8000/](http://localhost:8000/)**
- 📖 **Dokumentasi Teknis API (Swagger UI):** Buka di 👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**
- 📑 **Alternatif Redoc:** Buka di 👉 **[http://localhost:8000/redoc](http://localhost:8000/redoc)**

---

## 📡 Panduan API Endpoints

### 1. Generate Token JWT (`POST /api/v1/auth/token`)
Menghasilkan token otentikasi berdasarkan role pengguna:
```bash
curl -X POST "http://localhost:8000/api/v1/auth/token" \
     -H "Content-Type: application/json" \
     -d '{
       "user_id": "admin_01",
       "email": "admin@company.com",
       "role": "admin"
     }'
```

---

### 2. Tanya Jawab Dokumen (`POST /api/v1/rag/query`)
Mengajukan pertanyaan ke RAG pipeline dengan filter keamanan otomatis:
```bash
curl -X POST "http://localhost:8000/api/v1/rag/query" \
     -H "Authorization: Bearer <JWT_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "Bagaimana arsitektur Kubernetes dan CI/CD kita?",
       "top_k": 4,
       "filter_space": "ENG"
     }'
```

---

### 3. Ingest Dokumen Manual (`POST /api/v1/ingest/text`) *(Khusus Admin)*
Menambahkan potongan dokumen teks baru ke dalam Vector Store:
```bash
curl -X POST "http://localhost:8000/api/v1/ingest/text" \
     -H "Authorization: Bearer <ADMIN_JWT_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{
       "title": "SOP Monitoring Server",
       "content": "On-call engineer wajib merespons alert P1 dalam waktu 15 menit melalui Slack dan PagerDuty.",
       "space": "OPS",
       "source": "manual"
     }'
```

---

### 4. Sinkronisasi Confluence & Notion *(Khusus Admin)*
- **Confluence:** `POST /api/v1/ingest/confluence` (Menarik halaman dari space `ENG`, `HR`, `OPS`).
- **Notion:** `POST /api/v1/ingest/notion` (Menarik halaman dari database internal SOP dan Tech Docs).

---

### 5. Health Check (`GET /api/v1/health`)
Mengecek status kesehatan server, koneksi ChromaDB, dan koneksi Ollama:
```bash
curl -X GET "http://localhost:8000/api/v1/health"
```

---

## 🛠️ Panduan Pemecahan Masalah (Troubleshooting)

| Masalah | Penyebab | Solusi |
|---|---|---|
| `ModuleNotFoundError: No module named 'chromadb'` | Dependensi belum terinstal di environment Python aktif. | Jalankan `pip install -r requirements.txt` di dalam virtual environment (`venv`). |
| `Token tidak valid: Invalid crypto padding` | Tanda kutip ganda `"` ikut terbawa saat menyalin token. | Salin token murni tanpa tanda kutip di sekelilingnya (sistem juga sudah dilengkapi pembersih kutip otomatis). |
| `403 Forbidden` saat Ingest Data | Menggunakan token non-admin (`employee` / `engineering`). | Ganti role ke **`Admin`** pada switch bar dashboard atau generate token dengan role `admin`. |
| `Ollama unreachable / degraded` | Ollama belum berjalan atau model belum di-pull. | Jalankan perintah `ollama serve` dan pastikan model `llama3` serta `nomic-embed-text` telah di-pull. |

---

## 📄 Lisensi
Didistribusikan di bawah lisensi internal perusahaan.
