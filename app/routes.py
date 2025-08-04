from fastapi import APIRouter, UploadFile, File, Query
from app.services.insert_to_weaviate import weaviate_insertion
from app.services.weaviate_queries import *

router = APIRouter()

@router.post("/insert")
async def policy_insert(category: str, file: UploadFile = File(...)):
    return await weaviate_insertion(file, category)



# 4. Get all documents
@router.get("/documents")
async def list_all_documents(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    return await get_all_documents(limit, offset)


# 7. Hybrid search
@router.get("/search/hybrid")
async def hybrid_document_search(
    q: str = Query("Search query"),
    category: str = Query("All Categories"),
    alpha: float = Query(0.5, ge=0.0, le=1.0),
    limit: int = Query(5, ge=1, le=50)
):
    print("categories=====", category)
    if q and category != "All Categories":
        # Search within specific category
        print("hybrid search with category-----------")
        return await hybrid_search_with_category(q, category, limit, alpha)

    elif q and category == "All Categories":
        # Search across all categories
        print("hybrid search for all categories----------------")
        return await hybrid_search(q, limit, alpha)

    elif not q and category != "All":
        # No query, just filter by category
        print("search by category--------------")
        return await search_by_category(category, limit)
