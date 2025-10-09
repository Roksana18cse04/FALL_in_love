# delete schema
from fastapi import APIRouter, HTTPException
from app.services.schema_manager import delete_schema
from pydantic import BaseModel

class DeleteOrganizationRequest(BaseModel):
    organization: str = "HomeCare"

router = APIRouter()

@router.delete("/delete-organization")
async def delete_organization_endpoint(request: DeleteOrganizationRequest):
    try:
        return await delete_schema(request.organization)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error Deleting Organization: {str(e)}")