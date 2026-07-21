from fastapi import APIRouter

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/")
async def list_searches():
    """List search sessions or results.

    Returns:
        Placeholder search response.
    """
    return {"message": "Search endpoint placeholder"}
