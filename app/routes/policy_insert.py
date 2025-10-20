from fastapi import APIRouter, HTTPException
from app.services.weaviate_data_insertion import weaviate_insertion
from pydantic import BaseModel
from weaviate.exceptions import UnexpectedStatusCodeError

class Document(BaseModel):
    organization: str = "HomeCare"
    doc_id: str = "6"
    document_type: str = "policy"
    category: str
    object_key: str = "AI/policy/privacy_confidentiality_information_governance/provider-registration-policy.pdf"
    
router = APIRouter()

@router.post("/insert-document")
async def insert_document_endpoint(request: Document):
    try:
        response = await weaviate_insertion(
            request.organization,
            request.doc_id,
            request.document_type,
            request.object_key,
            request.category
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