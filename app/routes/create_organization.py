from fastapi import APIRouter, HTTPException
from app.services.schema_manager import create_schema
from pydantic import BaseModel

class CreateOrganizationRequest(BaseModel):
    organization: str = "HomeCare"

router = APIRouter()

@router.post("/create-organization")
async def create_organization_endpoint(request: CreateOrganizationRequest):
    try:
        return await create_schema(request.organization)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error Creating Organization: {str(e)}")
