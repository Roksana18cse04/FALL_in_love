
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
    object_key: str
    version: str = "v1"

@router.delete("/delete-document")
async def delete_document_endpoint(
    request: DeleteDocumentRequest
):
    try:
        response = await delete_weaviate_data(
            request.organization,
            request.object_key,
            request.version
        )
        logger.info("Deletion response: %s", response)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error Deleting document: {str(e)}")