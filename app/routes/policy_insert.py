from fastapi import APIRouter, Form, UploadFile, File
from app.services.weaviate_data_insertion import weaviate_insertion
from pydantic import BaseModel

class Document(BaseModel):
    organization: str = "HomeCare"
    doc_db_id: str = "123"
    document_type: str = "policy"
    document_url: str = "https://www.dropbox.com/scl/fi/i4js5sapbbihzkbejonzy/provider-registration-policy.pdf?rlkey=2egqmz4na3g5v44w3976lpgo2&st=vicm51sf&dl=1"
    summary: str = "This is a sample summary of the policy document."
    category: str = "privacy_confidentiality_information_governance"

router = APIRouter()

@router.post("/insert-document")
async def insert_document_endpoint(request: Document):
    return await weaviate_insertion(request.organization, request.doc_db_id, request.document_type, request.document_url, request.summary, request.category)
