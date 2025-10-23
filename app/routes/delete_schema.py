# delete schema
from fastapi import APIRouter, HTTPException
from app.services.schema_manager import delete_schema
from pydantic import BaseModel

class DeleteOrganizationRequest(BaseModel):
    organization_id: str

router = APIRouter()

@router.delete("/delete-organization")
async def delete_organization_endpoint(request: DeleteOrganizationRequest):
    try:
        organization = "Org_" + request.organization_id
        return await delete_schema(organization)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error Deleting Organization: {str(e)}")