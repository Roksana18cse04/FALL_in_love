from pydoc import text
from fastapi import APIRouter, Form, UploadFile, File, Query
from typing import Optional
from app.services.schema_manager import create_schema
from app.services.insert_to_weaviate import weaviate_insertion
from app.services.weaviate_queries import *
from pydantic import BaseModel
from app.services.bot import ask_doc_bot
from app.services.classification import classify_category
from app.services.summarize_pdf import summarize_with_gpt4
from app.services.extract_content import extract_content_from_pdf

router = APIRouter()


# Define a request model for structured input
class ChatRequest(BaseModel):
    organization: str
    question: str
    auth_token: str

@router.post("/chatbot")
async def chatbot_endpoint(request: ChatRequest):
    return await ask_doc_bot(request.question, request.organization, request.auth_token)

@router.post("/insert-policy")
async def policy_insert(
    organization: str = Form(...),
    category: str = Form(...),
    url: str = Form(...),
):
    return await weaviate_insertion(organization, url, category)

@router.get("/create-organization")
async def create_organization(organization: str):
    return await create_schema(organization)

@router.post("/get/summary-category")
async def get_summary(file: UploadFile = File(...)):
    # Implement your summary logic here
    try:
        text, title = await extract_content_from_pdf(file)
        summary = await summarize_with_gpt4(text, title)
        response = classify_category(docs_summary=summary)
        category = response.get("category", "Uncategorized")
        # upload to cloud storage
        # get url link

        return {
            "summary": summary,
            "category": category
            # "url": url
        }

    except Exception as e:
        return {"error": str(e)}
    
# delete file from cloud storage
# @router.delete("/delete-file")
# async def delete_file(file_id: str):
#     pass  # Implement delete logic here


# 4. Get all documents
# @router.get("/documents")
# async def list_all_documents(
#     limit: int = Query(20, ge=1, le=100),
#     offset: int = Query(0, ge=0)
# ):
#     return await get_all_documents(limit, offset)


# 7. Hybrid search
# @router.get("/search/hybrid")
# async def hybrid_document_search(
#     q: Optional[str] = Query(default=None),
#     category: str = Query("All Categories"),
#     alpha: float = Query(0.5, ge=0.0, le=1.0),
#     limit: int = Query(5, ge=1, le=50)
# ):
#     print("queries--------", q)
#     if q and category != "All Categories":
#         # Search within specific category
#         print("hybrid search with category-----------")
#         return await hybrid_search_with_category(q, category, limit, alpha)

#     elif q and category == "All Categories":
#         # Search across all categories
#         print("hybrid search for all categories----------------")
#         return await hybrid_search(q, limit, alpha)
    
#     elif not q and category == "All Categories":
#         print("get all documents for all categories------")
#         return await get_all_documents(limit)

#     elif not q and category != "All":
#         # No query, just filter by category
#         print("search by category--------------")
#         return await search_by_category(category, limit)
    

