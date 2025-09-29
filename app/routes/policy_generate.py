
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.services.policy_llm import generate_policy_with_vector_laws

router = APIRouter()

class PolicyRequest(BaseModel):
    title: str
    context: str

@router.post("/generate-policy")
async def generate_policy_endpoint(request: PolicyRequest):
    """
    Generate policy using super admin laws from Weaviate vector database.
    Automatically retrieves latest version laws and generates policy with strict adherence.
    """
    try:
        result = await generate_policy_with_vector_laws(
            title=request.title,
            context=request.context,
            version=None  # Use latest version
        )
        
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        
        return JSONResponse(content=result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating policy: {str(e)}")
