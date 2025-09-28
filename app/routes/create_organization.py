from fastapi import APIRouter
from app.services.schema_manager import create_schema
from pydantic import BaseModel

class CreateOrganizationRequest(BaseModel):
    organization: str = "HomeCare"

router = APIRouter()

@router.post("/create-organization")
async def create_organization_endpoint(request: CreateOrganizationRequest):
    return await create_schema(request.organization)
