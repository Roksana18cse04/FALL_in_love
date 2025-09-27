
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.services.policy_llm import generate_policy_json

router = APIRouter()

class PolicyRequest(BaseModel):
    context: str
    super_admin_law: str

@router.post("/generate-policy")
async def generate_policy_endpoint(request: PolicyRequest):
    policy_json = await generate_policy_json(request.context, request.super_admin_law)
    try:
        # Try to parse as JSON
        import json
        return JSONResponse(content=json.loads(policy_json))
    except Exception:
        # If not valid JSON, return as plain text
        return JSONResponse(content={"policy": policy_json})
