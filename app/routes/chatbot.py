# app/routers/chatbot.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from app.services.bot import ask_doc_bot

router = APIRouter()

class ChatRequest(BaseModel):
    organization: str = Field(default="HomeCare", description="Organization name")
    question: str = Field(..., min_length=1, description="User's question")
    auth_token: str = Field(..., min_length=1, description="Authentication token")

# @router.post("/chatbot")
# async def chatbot(request: ChatRequest):
#     try:
#         response = await ask_doc_bot(request.question, request.organization, request.auth_token)
#         return JSONResponse(content=response, status_code=200)
    
#     except Exception as e:
#         return JSONResponse(
#             status_code=500,
#             content={
#                 "status": "error",
#                 "message": "An unexpected server error occurred.",
#                 "error_code": "INTERNAL_SERVER_ERROR",
#                 "error_details": str(e)
#             }
#         )
@router.post("/chatbot")
async def chatbot(request: ChatRequest):
    try:
        # ask_doc_bot already returns a JSONResponse
        return await ask_doc_bot(request.question, request.organization, request.auth_token)
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "An unexpected server error occurred.",
                "error_code": "INTERNAL_SERVER_ERROR",
                "error_details": str(e)
            }
        )
