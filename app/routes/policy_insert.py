from fastapi import APIRouter, HTTPException
from app.services.weaviate_data_insertion import weaviate_insertion
from pydantic import BaseModel
from weaviate.exceptions import UnexpectedStatusCodeError

class Document(BaseModel):
    organization_id: str
    doc_id: str = "6"
    document_type: str = "policy"
    category: str
    title: str
    version_id: str = "1"
    version_number: int = 1
    content: str
    
router = APIRouter()

@router.post("/insert-document")
async def insert_document_endpoint(request: Document):
    try:
        organization = "org_" + request.organization_id
        response = await weaviate_insertion(
            organization,
            request.doc_id,
            request.document_type,
            request.content,
            request.category,
            request.title,
            request.version_id,
            request.version_number
        )
        return response
    except UnexpectedStatusCodeError as e:
        error_msg = str(e)
        if "429" in error_msg or "quota" in error_msg.lower():
            # OpenAI quota exceeded
            raise HTTPException(status_code=500,
                                detail = {
                                    "status": "error",
                                    "error_type": "quota_exceeded",
                                    "message": "System's OpenAI quota limit has been reached. Please wait or upgrade your plan."
                                })
        else:
            raise HTTPException(status_code=500,
                                detail = {
                                    "status": "error",
                                    "error_type": "weaviate_error",
                                    "message": error_msg
                                })
    except Exception as e:
        # Catch all for other exceptions
        raise HTTPException(
            status_code=500,
            detail= {
                "status": "error",
                "error_type": "internal_error",
                "message": str(e)
            })