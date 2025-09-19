from fastapi import APIRouter
from app.services.schema_manager import create_schema

router = APIRouter()

@router.get("/create-organization")
async def create_organization(organization: str):
    return await create_schema(organization)
