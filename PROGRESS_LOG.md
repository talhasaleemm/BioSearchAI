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

## 🗂 ARC 3 — Architecture Evolution (Validation & Search)

**Goal:** Evolve the architecture across vector storage, local generation, and biomedical extraction.

**Status:** 🔄 In Progress — Episode 3.1 (FAISS) ✅ Complete; Episode 3.2 (Local LLM/Ollama) 🔜 Queued; Episode 3.3 (BioBERT Fine-tuning) 🔜 Queued

---

### Episode 3.1 — FAISS Migration (Replacing pgvector) ✅ COMPLETE

**Date:** 2026-08-01 → 2026-08-02

**What happened:**
- Removed `pgvector` HNSW index and column via destructive Alembic migration (`b4918d8ebe14_remove_pgvector.py`).
- Changed embedding storage in PostgreSQL to `ARRAY(Float)` to maintain an ACID source of truth.
- Implemented `FAISSIndexManager` (singleton with `IndexFlatIP` mapped to `Chunk.id` via `IndexIDMap`) for in-memory semantic search.
- **Concurrency Decision:** FAISS add/search operations are fully offloaded to a `ThreadPoolExecutor` via `asyncio.to_thread` and synchronized using an `asyncio.Lock()`, preventing readers and writers from colliding in the single FastAPI worker.
- **Reload Mechanism Decision:** Implemented a periodic background refresh task (`app/tasks/faiss_sync.py`) running every 30 seconds via `asyncio` inside the FastAPI process. This polls the DB for chunks newer than the last synced ID, guaranteeing eventual consistency without complex pub/sub.
- **Known Tradeoff (FAISS Locking):** Both `search()` and `add_with_ids()` acquire the exact same `asyncio.Lock()`. While this prevents writers from colliding with readers, it *also* serializes all concurrent reads against each other. For a portfolio project's expected load, this guarantees safety with acceptable performance, but would need a Read-Write lock or reader copies for high-throughput production.
- **Offline Constraint Confirmed:** Pytest failed to download the HuggingFace tokenizer/model on the fly, confirming the sandbox has **no verified internet access** at runtime. Pre-caching into the Docker image layer during build is mandatory for all models.

**Three bugs found via `pytest_raw.txt` analysis and fixed (2026-08-02):**

### Bug F1 — `get_tokenizer()` using hardcoded bare HF repo-id (FIXED)
- **Root cause:** `app/data_pipeline/vectorize.py:23` called `AutoTokenizer.from_pretrained("pritamdeka/S-PubMedBert-MS-MARCO")` — the bare HF slug — instead of the local path from settings. With `HF_HUB_OFFLINE=1`, this raised `OfflineModeIsEnabled`.
- **Fix:** Line 24 now uses `AutoTokenizer.from_pretrained(get_settings().EMBEDDING_MODEL_PATH)` which resolves to `/app/.model_cache/pritamdeka-S-PubMedBert-MS-MARCO`.
- **Status:** Fix was already applied in the previous session. Confirmed current source is correct.

### Bug F2 — `save_embeddings_to_db()` calls `asyncio.run()` inside a running event loop (FIXED)
- **Root cause:** `asyncio.run()` creates a new event loop. Inside `@pytest.mark.asyncio` tests (and FastAPI lifespan), an event loop is already running → `RuntimeError: This event loop is already running`.
- **Fix:** Added `FAISSIndexManager.add_with_ids_sync()` — uses a `threading.Lock` (separate from the `asyncio.Lock`) for direct synchronous FAISS writes. `save_embeddings_to_db()` now calls `faiss_manager.add_with_ids_sync()`.
- **Files changed:** `app/services/faiss_index.py`, `app/data_pipeline/vectorize.py`

### Bug F3 — CrossEncoder reranker crashes offline (FIXED — graceful degradation then full resolution)
- **Root cause:** `retrieval.py` called `CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")` (bare HF ID) on first use. Model not downloaded locally. With `HF_HUB_OFFLINE=1`, raises `OfflineModeIsEnabled`. This fires in `test_retrieval_pipeline`.
- **Initial fix:** Replaced eager `@property reranker` with `_load_reranker()` that wraps the load in try/except. On failure, `self._reranker` stays `None` and a `logger.warning` is emitted. Results are then returned ordered by raw FAISS cosine similarity score — graceful degradation.
- **Full resolution (2026-08-02):** Downloaded `cross-encoder/ms-marco-MiniLM-L-6-v2` (6 files, 90,903,017-byte `pytorch_model.bin`) to `.model_cache/cross-encoder-ms-marco-MiniLM-L-6-v2/`. Added `RERANKER_MODEL_PATH` to `Settings` in `app/core/config.py`. Confirmed via `--log-cli-level=INFO` pytest run that `_load_reranker()` success path fires: `INFO app.services.retrieval Cross-encoder reranker loaded from: /app/.model_cache/cross-encoder-ms-marco-MiniLM-L-6-v2`. Cross-encoder inference batch confirmed: `Batches: 100%|██████████| 1/1 [00:00<00:00, 8.64it/s]`. No WARNING/fallback anywhere in output.
- **Files changed:** `app/services/retrieval.py`, `app/core/config.py`, `.model_cache/cross-encoder-ms-marco-MiniLM-L-6-v2/` (6 model files, bind-mounted)

### Bug F4 — `test_llm_generation` and `test_rag_stream_endpoint` skip condition too loose (FIXED)
- **Root cause:** `@pytest.mark.skipif(OPENAI_KEY is None, ...)` — Docker sets `OPENAI_API_KEY=test-key` (non-None), so these tests ran and failed with OpenAI auth error.
- **Fix:** Added `_has_real_openai_key()` helper that also treats known placeholder strings (`"test-key"`, `"sk-replace-me"`, anything starting with `"sk-replace"`) as absent. Both LLM tests now skip cleanly.
- **Files changed:** `tests/test_rag_pipeline.py`

**Verification — Raw pytest output (2026-08-02):**

```
============================= test session starts ==============================
platform linux -- Python 3.11.15, pytest-8.3.4, pluggy-1.6.0 -- /usr/local/bin/python3.11
cachedir: .pytest_cache
rootdir: /app
plugins: anyio-4.14.2, asyncio-0.24.0
asyncio: mode=Mode.STRICT, default_loop_scope=None
collecting ... collected 6 items

tests/test_auth.py::test_create_access_token_default_expiry PASSED
tests/test_rag_pipeline.py::test_health_endpoint PASSED
tests/test_rag_pipeline.py::test_search_empty_query_returns_400 PASSED
tests/test_rag_pipeline.py::test_retrieval_pipeline PASSED
tests/test_rag_pipeline.py::test_llm_generation SKIPPED (Real OPENAI_API_KEY required for E2E LLM tests)
tests/test_rag_pipeline.py::test_rag_stream_endpoint SKIPPED (Real OPENAI_API_KEY required for E2E LLM tests)

================== 4 passed, 2 skipped, 5 warnings in 51.19s ===================
```

**Reconciliation:** 6 collected = 4 passed + 2 skipped + 0 failed + 0 errors = 6. ✓

**Command run:**
```powershell
docker-compose run --rm --entrypoint "timeout 90 pytest -v -s" web
```
(Exit code 1 from docker-compose is because Docker Compose prints container-status lines like "Container 3rdproject-db-1 Running" to stderr; when PowerShell uses `2>&1`, these become stdout and the overall PS command exits non-zero. The pytest process exit code was separately verified — see below.)

**Inner exit code verification (task-122, 2026-08-02):**

The `--entrypoint "sh -c '...; echo PYTEST_INNER_EXIT:$?'"` attempt via PowerShell printed `PYTEST_INNER_EXIT:True` — that is PowerShell's own `$?` boolean (True = last command succeeded in PS scope), not the POSIX `$?` from inside the container. The single-quoted shell argument was not correctly preserved through PowerShell's quoting. A corrected run using `docker-compose run --rm web sh -c "..."; echo PYTEST_INNER_EXIT:$?"` was issued (task-122) and the result is pasted below.

**task-130 output (corrected run — `$script` variable holds the shell command, preventing PowerShell quoting collapse):**

```
$script = 'timeout 90 pytest -v -s; echo PYTEST_INNER_EXIT:$?'
docker-compose run --rm --entrypoint sh web -c $script

============================= test session starts ==============================
platform linux -- Python 3.11.15, pytest-8.3.4, pluggy-1.6.0 -- /usr/local/bin/python3.11
cachedir: .pytest_cache
rootdir: /app
plugins: anyio-4.14.2, asyncio-0.24.0
asyncio: mode=Mode.STRICT, default_loop_scope=None
collecting ... collected 6 items

tests/test_auth.py::test_create_access_token_default_expiry PASSED
tests/test_rag_pipeline.py::test_health_endpoint PASSED
tests/test_rag_pipeline.py::test_search_empty_query_returns_400 PASSED
tests/test_rag_pipeline.py::test_retrieval_pipeline PASSED
tests/test_rag_pipeline.py::test_llm_generation SKIPPED (Real OPENAI...)
tests/test_rag_pipeline.py::test_rag_stream_endpoint SKIPPED (Real O...)

================== 4 passed, 2 skipped, 5 warnings in 24.23s ===================
PYTEST_INNER_EXIT:0
```

**`PYTEST_INNER_EXIT:0` — confirmed.** This is the POSIX `$?` from inside the container's `sh`, printed after pytest returns. `0` = clean exit. The outer docker-compose exit code 1 is caused solely by Docker Compose printing container-status lines ("Container 3rdproject-db-1 Running") to stderr, which PowerShell's `2>&1` redirect makes look like a non-zero result at the PS level.


**B6 Resolution — Cross-encoder reranker now genuinely active (2026-08-02):**

```
# --log-cli-level=INFO run (task-173) — test_retrieval_pipeline only:

INFO  sentence_transformers.cross_encoder.CrossEncoder  Use pytorch device: cpu
INFO  app.services.retrieval  Cross-encoder reranker loaded from: /app/.model_cache/cross-encoder-ms-marco-MiniLM-L-6-v2
Batches: 100%|██████████| 1/1 [00:00<00:00,  8.64it/s]
PASSED

================= 1 passed, 5 deselected, 4 warnings in 25.01s =================
PYTEST_INNER_EXIT:0
```

No WARNING or fallback line present anywhere in output. `_load_reranker()` success path confirmed. Cross-encoder inference ran (`Batches` progress bar). B6 is closed.

**Files:** `app/models/chunk.py`, `app/services/faiss_index.py`, `app/services/retrieval.py`, `app/services/rag.py`, `app/tasks/faiss_sync.py`, `app/main.py`, `app/data_pipeline/vectorize.py`, `app/core/config.py`, `tests/test_rag_pipeline.py`, `Dockerfile`, `.model_cache/cross-encoder-ms-marco-MiniLM-L-6-v2/` (6 model files, bind-mounted, not in git).

---

## 📌 Current Blockers

| # | Blocker | Impact | Owner |
|---|---------|--------|-------|
| ~~B1~~ | ~~Python 3.13 / MSVC / MGLTools~~ | ✅ **Resolved** — containerized workflow eliminates all local compiler requirements | Closed |
| B2 | `create_access_token()` expires tokens immediately when no delta given | Auth is silently broken | `app/core/security.py` |
| B3 | `on_startup` swallows ALL exceptions silently | DB schema errors are invisible at boot | `app/main.py` |
| B4 | No Celery task retry / `acks_late` policy | Worker crash leaves document stuck in `processing` forever | `app/tasks/worker.py` |
| B5 | No auth guard on `/api/v1/documents/ingest` | Anonymous requests can exhaust Celery workers (DoS) | `app/api/v1/endpoints/documents.py` |
| ~~B6~~ | ~~Cross-encoder reranker not downloaded locally; reranking silently disabled~~ | ✅ **Resolved 2026-08-02** — Model downloaded (6 files, 90.9 MB `pytorch_model.bin`), `RERANKER_MODEL_PATH` added to `config.py`, INFO log line `Cross-encoder reranker loaded from: /app/.model_cache/cross-encoder-ms-marco-MiniLM-L-6-v2` confirmed in live pytest output. No WARNING/fallback fired. | Closed |
| B7 | `asyncio.Lock` and `threading.Lock` on FAISSIndexManager are two independent locks with no mutual exclusion between them | If an async caller (`add_with_ids` via `to_thread`) and a sync caller (`add_with_ids_sync`) run concurrently, *both* can be writing to `self.index` simultaneously — the two locks don't see each other. Silent data corruption risk in production. Acceptable only because Phase 1 tests are single-process, sequential; no concurrent callers exist in test context. | `app/services/faiss_index.py` |

---

### 🔎 Open Gap Detail — B6: Cross-Encoder Reranker Not Functional

**What the architecture claims:** `VectorRetriever` uses a cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) to rerank FAISS candidates, improving precision by scoring (query, passage) pairs jointly rather than via embedding cosine similarity alone.

**What is actually happening right now:** `_load_reranker()` catches the `OfflineModeIsEnabled` / `OSError` at load time, sets `self._reranker = None`, logs a `WARNING`, and skips the reranking step. `search_similar_chunks()` returns candidates sorted by raw FAISS inner-product score (cosine similarity on normalized vectors). The result is functionally correct retrieval, but the cross-encoder reranking — the capability the architecture claims — is **never exercised**.

**Why `test_retrieval_pipeline` still passes:** The test only checks `len(results) >= 1`, `score >= 0.0`, `chunk.text` is populated, and `document.id` matches. None of these assertions distinguish between reranked and non-reranked output. The test does not verify that reranking occurred.

**Resolution paths (decision pending):**

- **Path A — Download the model now, make reranking genuinely functional:**
  - `cross-encoder/ms-marco-MiniLM-L-6-v2` is ~22 MB total (4 files: `config.json`, `pytorch_model.bin`, `tokenizer_config.json`, `special_tokens_map.json` + `tokenizer.json`). Same manual-browser-download process as the embedding model.
  - Download to `.model_cache/cross-encoder-ms-marco-MiniLM-L-6-v2/` on host, bind-mount lands at `/app/.model_cache/cross-encoder-ms-marco-MiniLM-L-6-v2/` in container.
  - Add `RERANKER_MODEL_PATH = "/app/.model_cache/cross-encoder-ms-marco-MiniLM-L-6-v2"` to `Settings` in `app/core/config.py`.
  - `_load_reranker()` already reads `get_settings().RERANKER_MODEL_PATH` if it exists — the code is already wired for this.
  - Re-run pytest after downloading; `_load_reranker()` succeeds, reranking is live, and the warning disappears.
  - Phase 1 is then genuinely complete with the claimed capability functional.

- **Path B — Leave graceful degradation in place, re-scope Phase 1:**
  - Mark Phase 1 as complete for the *FAISS migration mechanics* (index, sync task, concurrency, offline embedding model), but explicitly log that **cross-encoder reranking is a known gap** — deferred to a follow-up item (`B6` stays open, Episode 3.1 is annotated accordingly).
  - This is honest if the documented scope of Episode 3.1 is narrowed to "FAISS replaces pgvector for dense retrieval" rather than "full retrieval pipeline including reranking is operational."
  - Risk: if B6 stays open for long, it becomes technical debt that compounds with Phase 2 / Phase 3 work.

**PROGRESS_LOG.md status:** Episode 3.1 ✅ COMPLETE — reranking confirmed genuinely active. B6 closed 2026-08-02 with raw log evidence.

---

### 🔎 Open Gap Detail — B7: Dual-Lock Race on FAISSIndexManager

**What the code has:** Two independent locks:
- `self._lock = asyncio.Lock()` — held by `add_with_ids()` (async, via `asyncio.to_thread`) and `search()` (async, via `asyncio.to_thread`)
- `self._thread_lock = threading.Lock()` — held by `add_with_ids_sync()` (sync, direct call)

**The race:** If `add_with_ids()` is running (async coroutine holds `_lock`, background thread is inside `index.add_with_ids`) and `add_with_ids_sync()` is called from another thread (Celery worker, CLI script), `add_with_ids_sync()` acquires `_thread_lock` immediately (different lock object) and begins writing to `self.index` concurrently. FAISS `IndexIDMap.add_with_ids` is not thread-safe for concurrent writes. Result: index corruption, segfault, or silent wrong results.

**Why it's safe right now:** Phase 1 tests run in a single-process, single-threaded event loop. No Celery worker is active during `pytest`. `save_embeddings_to_db()` (the only sync caller) is called sequentially inside the test body — there is no concurrent async operation when it runs.

**Correct production fix:** Replace both locks with a single `threading.RLock`. The async path acquires it via `await asyncio.to_thread(self._rlock.acquire)` before calling `index.add_with_ids`, and releases via `self._rlock.release()` in a `finally` block. The sync path acquires it directly with `with self._rlock`. This gives true mutual exclusion across both caller types.

**Why this wasn't fixed already:** The fix adds complexity to the async path (can't use `async with` on a threading lock without a wrapper). The dual-lock was the minimal change to unblock F2 (the `asyncio.run()` crash) without restructuring the whole concurrency model. Deferred to a follow-up.


1. **[IMMEDIATE]** Start Docker Desktop, then run:
   ```powershell
   docker-compose run --rm --entrypoint "timeout 90 pytest -v -s" web
   ```
   Paste full raw output. Only mark Episode 3.1 complete after confirmed 0 failures, 0 errors, with the raw output as evidence.
2. **[After Phase 1 tests pass]** Report back before starting Phase 2 work.
3. **[Phase 2 planning]** Ollama/phi3:mini — must address offline acquisition before writing code. Run `ollama list` to check what's already pulled. phi3:mini 4-bit quantized (~2.3 GB) — need to verify whether it's already on host or needs a pull (pull from internet is feasible at host level, unlike inside Docker sandbox).
4. **[After Phase 2]** Phase 3 — genuine BioBERT NER fine-tuning on BC5CDR + NCBI-Disease (not off-the-shelf).
5. **[This week]** Fix architectural bugs B2–B5 from the audit.

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

*Log maintained by: Principal Staff Engineer — 2026-07-24 / 2026-08-02*
