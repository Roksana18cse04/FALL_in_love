from fastapi import APIRouter, Query
from app.services.weaviate_queries import get_all_documents
from typing import Optional

router = APIRouter()

@router.get("/documents")
async def list_all_documents(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    return await get_all_documents(limit, offset)
