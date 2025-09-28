# delete schema
from fastapi import APIRouter
from app.services.schema_manager import delete_schema
from pydantic import BaseModel

class DeleteOrganizationRequest(BaseModel):
    organization: str = "HomeCare"

router = APIRouter()

@router.delete("/delete-organization")
async def delete_organization_endpoint(request: DeleteOrganizationRequest):
    return await delete_schema(request.organization)