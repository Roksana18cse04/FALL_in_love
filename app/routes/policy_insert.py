from fastapi import APIRouter, Form, UploadFile, File
from app.services.insert_to_weaviate import weaviate_insertion

router = APIRouter()

@router.post("/insert-policy")
async def policy_insert(
    organization: str = Form(...),
    category: str = Form(...),
    file: UploadFile = File(...)
):
    return await weaviate_insertion(organization, file, category)
