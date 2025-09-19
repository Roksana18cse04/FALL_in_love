from fastapi import APIRouter, Query
from typing import Optional
from app.services.weaviate_queries import hybrid_search, hybrid_search_with_category

router = APIRouter()

@router.get("/search/hybrid")
async def hybrid_document_search(
    q: Optional[str] = Query(default=None),
    category: str = Query("All Categories"),
    alpha: float = Query(0.5, ge=0.0, le=1.0),
    limit: int = Query(5, ge=1, le=50)
):
    if q and category != "All Categories":
        return await hybrid_search_with_category(q, category, limit, alpha)
    elif q and category == "All Categories":
        return await hybrid_search(q, limit, alpha)
