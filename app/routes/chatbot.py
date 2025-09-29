from fastapi import APIRouter
from pydantic import BaseModel
from app.services.bot import ask_doc_bot

router = APIRouter()

class ChatRequest(BaseModel):
    organization: str = "HomeCare"
    question: str = "Who can apply to be a registered provider under this policy?"
    auth_token: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzYwODUzMTU5LCJpYXQiOjE3NTgyNjExNTksImp0aSI6ImExM2ExOGI0YWIwNTRmMWI5NDUxMDVlYmZiMTE0NTRmIiwidXNlcl9pZCI6IjcifQ.iHJDqnwOyfJDNQbwF-3kI4fH4bif-37mIElm_ZC4hxA"

@router.post("/chatbot")
async def chatbot_endpoint(request: ChatRequest):
    return await ask_doc_bot(request.question, request.organization, request.auth_token)
