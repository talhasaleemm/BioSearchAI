import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.models import Base
from app.models.user import User  # noqa: F401
from app.models.search_session import SearchSession  # noqa: F401
from app.models.session_action import SessionAction  # noqa: F401
from app.models.document import Document  # noqa: F401
from app.models.chunk import Chunk  # noqa: F401
from app.routers import auth, search, history
from app.api.v1.endpoints import search as search_v1
from app.api.v1.endpoints import rag as rag_v1
from app.api.v1.endpoints import documents as documents_v1
from app.api.v1.endpoints import sessions as sessions_v1
import asyncio

# Configure root logger so logging.info() lines from services (retrieval, NER) 
# appear in Railway stdout alongside Uvicorn's access logs.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    force=True,
)


from app.tasks.faiss_sync import periodic_faiss_sync
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.models import engine
    # Let exceptions bubble up to fail startup properly if DB connection fails
    Base.metadata.create_all(bind=engine)
    if not settings.DISABLE_BACKGROUND_TASKS:
        # Start the FAISS background sync task
        sync_task = asyncio.create_task(periodic_faiss_sync(interval_seconds=30))
        yield
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass
    else:
        yield

app = FastAPI(title="BioSearchAI", version="0.1.0", lifespan=lifespan)

settings = get_settings()
cors_origins = [
    origin.strip() 
    for origin in settings.CORS_ALLOWED_ORIGINS.split(",") 
    if origin.strip()
]

if not cors_origins:
    raise RuntimeError(
        "CORS_ALLOWED_ORIGINS cannot be empty. Wildcard CORS (['*']) with "
        "allow_credentials=True is insecure and disallowed. Configure an explicit "
        "origin list or the app will refuse to start."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(search.router)
app.include_router(history.router)
app.include_router(search_v1.router)
app.include_router(rag_v1.router)
app.include_router(documents_v1.router)
app.include_router(sessions_v1.router, prefix="/api/v1/sessions", tags=["sessions"])


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


