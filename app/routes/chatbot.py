from fastapi import APIRouter
from pydantic import BaseModel
from app.services.bot import ask_doc_bot

router = APIRouter()

class ChatRequest(BaseModel):
    organization: str = "HomeCare"
    question: str = "What is the policy on data privacy?"
    auth_token: str = "your_auth_token"

@router.post("/chatbot")
async def chatbot_endpoint(request: ChatRequest):
    return await ask_doc_bot(request.question, request.organization, request.auth_token)
