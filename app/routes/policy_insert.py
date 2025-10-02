from fastapi import APIRouter, Form, UploadFile, File
from app.services.weaviate_data_insertion import weaviate_insertion
from pydantic import BaseModel

class Document(BaseModel):
    organization: str = "HomeCare"
    doc_db_id: str = "123"
    document_type: str = "policy"
    document_object_key: str = "AI/policy/privacy_confidentiality_information_governance/provider-registration-policy.pdf"
    summary: str = "This is a sample summary of the policy document."
    category: str = "privacy_confidentiality_information_governance"

router = APIRouter()

@router.post("/insert-document")
async def insert_document_endpoint(request: Document):
    return await weaviate_insertion(request.organization, request.doc_db_id, request.document_type, request.document_object_key, request.summary, request.category)
