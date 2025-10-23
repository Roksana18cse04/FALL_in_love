from fastapi import APIRouter, HTTPException
from app.services.schema_manager import create_schema
from pydantic import BaseModel

class CreateOrganizationRequest(BaseModel):
    organization_id: str

router = APIRouter()

@router.post("/create-organization")
async def create_organization_endpoint(request: CreateOrganizationRequest):
    try:
        organization = "Org_" + request.organization_id
        return await create_schema(organization)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error Creating Organization: {str(e)}")
