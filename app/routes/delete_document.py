
# remove weaviate data

from fastapi import APIRouter, HTTPException
import logging
from app.services.weaviate_data_deletion import delete_weaviate_data
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

class DeleteDocumentRequest(BaseModel):
    organization: str = "HomeCare"
    category: str = "privacy_confidentiality_information_governance"
    document_type: str = "policy"
    filename: str = "Provider registration policy"
    version: str = "v1"
    s3version_id: str

@router.delete("/delete-document")
async def delete_document_endpoint(
    request: DeleteDocumentRequest
):
    try:
        response = await delete_weaviate_data(
            request.organization,
            request.category,
            request.document_type,
            request.filename,
            request.version,
            request.s3version_id
        )
        logger.info("Deletion response: %s", response)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error Deleting document: {str(e)}")