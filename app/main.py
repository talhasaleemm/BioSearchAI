from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.models.base import Base
from app.models.user import User  # noqa: F401
from app.models.search_session import SearchSession  # noqa: F401
from app.models.session_action import SessionAction  # noqa: F401
from app.models.document import Document  # noqa: F401
from app.models.chunk import Chunk  # noqa: F401
from app.routers import auth, search, history

settings = get_settings()
app = FastAPI(title="BioSearchAI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(search.router)
app.include_router(history.router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.on_event("startup")
async def on_startup() -> None:
    from app.models.base import engine
    Base.metadata.create_all(bind=engine)
