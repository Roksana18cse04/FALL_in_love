
# remove weaviate data

from fastapi import APIRouter, HTTPException
import logging
from app.services.weaviate_data_deletion import delete_weaviate_data
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

class DeleteDocumentRequest(BaseModel):
    organization_id: str
    document_id: str = "6"
    version_id: str = "1"

@router.delete("/delete-document")
async def delete_document_endpoint(
    request: DeleteDocumentRequest
):
    try:
        organization = "Org_" + request.organization_id
        response = await delete_weaviate_data(
            organization,
            request.document_id,
            request.version_id
        )
        logger.info("Deletion response: %s", response)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error Deleting document: {str(e)}")