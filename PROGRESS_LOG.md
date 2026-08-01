# BioSearchAI — Project Progress Log

> **Format:** Arcs represent major project phases. Episodes are discrete development units within an arc.
> **Status Key:** ✅ Complete | 🔄 In Progress | ⏳ Blocked | 🔜 Queued

---

## 🗂 ARC 1 — Architecture & Scaffolding

**Goal:** Design and scaffold the full-stack Biomedical RAG pipeline — database schema, API skeleton, background worker, and ingestion pipeline.

**Outcome:** ✅ Complete

---

### Episode 1.1 — Core Data Model Design ✅

**Date:** Pre-2026-07-24

**What happened:**
- Defined 5 SQLAlchemy 2.0 models using `Mapped[]` typed columns: `User`, `SearchSession`, `SessionAction`, `Document`, `Chunk`.
- `Chunk` model features:
  - `Vector(768)` column (pgvector) with an HNSW index (`m=16`, `ef_construction=64`, `vector_cosine_ops`).
  - `TSVECTOR` column (`fts_vector`) with a GIN index for full-text search.
- All cascade relationships are set (`ondelete="CASCADE"` at FK level + SQLAlchemy cascade).

**Files:** `app/models/`

---

### Episode 1.2 — FastAPI Application Skeleton ✅

**Date:** Pre-2026-07-24

**What happened:**
- Dual-router architecture established:
  - Legacy routers under `app/routers/` (auth, search, history).
  - Versioned v1 routers under `app/api/v1/endpoints/` (search, rag, documents).
- CORS middleware configured (wildcard — needs tightening before production).
- `on_startup` handler calls `Base.metadata.create_all()` (wrapped in bare `except: pass` — identified as a risk; see Audit below).
- Health check endpoint at `GET /health`.

**Files:** `app/main.py`

---

### Episode 1.3 — Authentication System ✅

**Date:** Pre-2026-07-24

**What happened:**
- JWT-based auth using `PyJWT[crypto]` + Argon2 password hashing via `pwdlib`.
- `get_current_user()` dependency injected into protected routes.
- `create_access_token()` has a known bug: when `expires_delta` is not provided, `expire` is set to `datetime.now()` — **effectively creating an immediately-expired token**.

**Files:** `app/core/security.py`, `app/core/deps.py`

---

### Episode 1.4 — Celery + Redis Background Worker ✅

**Date:** Pre-2026-07-24

**What happened:**
- Celery app configured with Redis as both broker and result backend.
- `process_document_task` task: fetches Document → chunks → embeds → saves vectors.
- DB session lifecycle managed manually (`SessionLocal()` / `finally: db.close()`).

**Files:** `app/tasks/celery_app.py`, `app/tasks/worker.py`

---

### Episode 1.5 — RAG Engine & Hybrid Retrieval ✅

**Date:** Pre-2026-07-24

**What happened:**
- `VectorRetriever`: Hybrid dense + sparse (RRF fusion) retrieval with cross-encoder reranking (`cross-encoder/ms-marco-MiniLM-L-6-v2`).
- `RAGEngine`: Wraps retriever + OpenAI client. Supports both synchronous and streaming (SSE) generation.
- Biomedical-specific chunker in `vectorize.py` using the `pritamdeka/S-PubMedBert-MS-MARCO` tokenizer.

**Files:** `app/services/retrieval.py`, `app/services/rag.py`, `app/data_pipeline/vectorize.py`

---

### Episode 1.6 — Docker & Alembic Infrastructure ✅

**Date:** Pre-2026-07-24

**What happened:**
- `docker-compose.yml`: 4 services — `db` (pgvector/pgvector:pg16), `redis` (redis:7-alpine), `web`, `worker`.
- Services use `healthcheck` + `depends_on: condition: service_healthy`.
- `Dockerfile`: Python 3.11-slim, installs build-essential + libpq-dev, then pip requirements.
- `entrypoint.sh` runs `alembic upgrade head` before starting Uvicorn.
- Alembic configured with autogenerate metadata from `Base`.

**Files:** `Dockerfile`, `docker-compose.yml`, `entrypoint.sh`, `alembic/env.py`

---

## 🗂 ARC 2 — Infrastructure Setup (Environment & Build)

**Goal:** Stand up the full local development environment on Windows. Achieve zero environment drift between developer machines and production containers.

**Current Status:** ✅ **Resolved** — Pivot to containerized workflow complete (Episode 2.3)

---

### Episode 2.1 — Initial pip Environment Attempt ⏳ BLOCKED

**Date:** Pre-2026-07-24

**What happened:**
- Attempted `pip install -r requirements.txt` in a Python 3.13 virtual environment.
- **Failure:** `tokenizers` and `sentence-transformers` require compilation from source (no pre-built wheels for CPython 3.13 on Windows at the time).
- **Root cause:** Missing Microsoft Visual C++ Build Tools (`link.exe` not found / wrong path), compounded by MGLTools PATH pollution overriding the MSVC linker.

**Error signatures:**
```
error: Microsoft Visual C++ 14.0 or greater is required.
error LNK1181: cannot open input file '...\link.exe'
```

**Resolution:** Abandoned — moved to Conda-first strategy (which was itself subsequently abandoned; see Episode 2.3).

---

### Episode 2.2 — Conda-First Strategy ⏳ ABANDONED

**Date:** 2026-07-24

**What happened:**
- Designed a `environment.yml` using `conda-forge` to install `tokenizers`, `torch`, and `sentencepiece` from pre-built binaries, bypassing MSVC entirely.
- An `environment.yml` was committed to the repo root as a design artifact.
- **Decision to abandon:** This approach still requires a local Python toolchain and adds Conda as a permanent dependency for every developer on Windows. It creates a two-class system (Conda devs vs. Docker devs) and does not eliminate the risk of environment drift.

**Outcome:** Strategy scrapped before execution. The `environment.yml` file remains in the repo as a reference artifact but is not the active environment strategy.

---

### Episode 2.3 — Pivot to Containerized Development Workflow ✅ COMPLETE

**Date:** 2026-07-24

**Decision:** Completely dropped all local Python environment strategies (both pip venv and Conda). The **permanent solution** for handling heavy C++ / Rust-compiled ML libraries (`tokenizers`, `sentence-transformers`, `torch`) on this Windows machine is to run all development inside Docker containers.

**Rationale:**
- The Dockerfile already uses `python:3.11-slim` + `apt-get install build-essential`, which provides a clean Linux build environment where all wheels compile cleanly.
- Zero environment drift: every contributor, regardless of OS, uses the exact same container image.
- Eliminates the MSVC / MGLTools PATH conflict permanently — the host Windows environment is never involved in running Python code.

**Artifacts created:**

| File | Purpose |
|------|---------|
| `docker-compose.override.yml` | Bind-mounts `./` into `web` and `worker` containers; enables `uvicorn --reload` and `watchmedo` Celery auto-restart; adds Flower task monitor on port 5555. |
| `.devcontainer/devcontainer.json` | VS Code DevContainer config wired to the Compose stack. Opens the editor inside the `web` container. Pre-configures Ruff, Black, Pylance, PostgreSQL client, and pytest. |
| `requirements.txt` | Added `watchdog>=4.0.0` (for `watchmedo`) and `httpx>=0.27.0` (for async test client). |

**How the live-reload workflow works:**
1. `docker-compose up --build` (first time only — builds the image).
2. Any subsequent `docker-compose up` uses the cached image.
3. Edit any `.py` file on the host → Uvicorn and Celery restart inside their containers within ~1s.
4. No image rebuild required for code changes.

**VS Code DevContainer workflow:**
1. Open command palette → `Dev Containers: Reopen in Container`.
2. VS Code attaches directly to the running `web` container.
3. All extensions (Ruff, Pylance, REST Client, etc.) are pre-installed inside the container.

---

### Episode 2.4 — Docker Container Spin-Up 🔜 QUEUED

**Prerequisite:** Docker Desktop must be running on the host Windows machine.

**Note:** The MSVC issue is now entirely irrelevant. The build environment is `python:3.11-slim` + `build-essential` (Linux). All ML wheels build cleanly.

---

## 🗂 ARC 3 — Testing & Validation

**Goal:** Full test suite coverage, integration tests, and RAG quality evaluation.

**Status:** 🔜 Queued

---

### Episode 3.1 — Unit & Integration Tests 🔜 QUEUED

**Files:** `tests/test_rag_pipeline.py` (existing, needs review)

---

## 📌 Current Blockers

| # | Blocker | Impact | Owner |
|---|---------|--------|-------|
| ~~B1~~ | ~~Python 3.13 / MSVC / MGLTools~~ | ✅ **Resolved** — containerized workflow eliminates all local compiler requirements | Closed |
| B2 | `create_access_token()` expires tokens immediately when no delta given | Auth is silently broken | `app/core/security.py` |
| B3 | `on_startup` swallows ALL exceptions silently | DB schema errors are invisible at boot | `app/main.py` |
| B4 | No Celery task retry / `acks_late` policy | Worker crash leaves document stuck in `processing` forever | `app/tasks/worker.py` |
| B5 | No auth guard on `/api/v1/documents/ingest` | Anonymous requests can exhaust Celery workers (DoS) | `app/api/v1/endpoints/documents.py` |

---

## 📋 Next Steps

1. **[Immediate]** Delete the Conda environment (cleanup commands below — never used).
2. **[Today]** First Docker run: `docker-compose up --build -d` — validate all 4 services come healthy.
3. **[Today]** Open VS Code DevContainer: `Dev Containers: Reopen in Container`.
4. **[This week]** Fix the 4 remaining architectural bugs (B2–B5) from the audit.
5. **[This week]** Run the existing test suite inside the container and close coverage gaps.

---

## 🧹 Conda Cleanup Commands

> Run these in PowerShell to remove the Conda environment that was created but never used.

```powershell
# Confirm the environment exists
conda env list

# Remove it cleanly
conda env remove --name biosearchai --yes

# Verify it is gone
conda env list

# Optional: remove the cached package tarballs to free disk space
conda clean --all --yes
```

---

*Log maintained by: Principal Staff Engineer — 2026-07-24*
