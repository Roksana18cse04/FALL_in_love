"""
Updated FastAPI route with organization_type parameter and fixed Pydantic validation
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.services.policy_llm import generate_policy_html

router = APIRouter()


class PolicyGenerationRequest(BaseModel):
    title: str
    context: str
    organization_type: str
    target_words: int = 3000


class PolicyGenerationResponse(BaseModel):
    generated_content: Optional[str] = None  # Make optional
    word_count: int
    success: bool
    error_message: Optional[str] = None  # Make optional
    original_context: str


@router.post("/generate-html", response_model=PolicyGenerationResponse)
async def generate_policy_content(request: PolicyGenerationRequest):
    """
    Generate policy content in HTML format with professional inline styling.
    Returns HTML-formatted content with inline CSS (no embedded <style> tags).
    
    Args:
        request: PolicyGenerationRequest containing:
            - title: Policy title
            - context: Policy context/description
            - target_words: Target word count (default: 3000)
            - organization_type: Collection name in Weaviate
        
    Returns:
        PolicyGenerationResponse with:
            - generated_content: HTML with inline styles
            - word_count: Actual word count
            - success: True/False
            - error_message: Error details if failed
            - original_context: Original input context
    
    Example:
        POST /policy/generate-html
        {
            "title": "Data Privacy Policy",
            "context": "Policy for handling customer data",
            "target_words": 3000,
            "organization_type": "HomeCareAct"
        }
    """
    try:
        result = await generate_policy_html(
            title=request.title,
            context=request.context,
            organization_type=request.organization_type,
            target_words=request.target_words
        )
        print("generate_policy_content result:", result.get("generated_content")[:200] if result.get("generated_content") else "None")
        
        return PolicyGenerationResponse(
            generated_content=result.get("generated_content"),
            word_count=result.get("word_count", 0),
            success=result.get("success", False),
            error_message=result.get("error_message"),  # Can now be None
            original_context=result.get("original_context", "")
        )
    except Exception as e:
        print(f"Route error: {str(e)}")
        import traceback
        traceback.print_exc()
        return PolicyGenerationResponse(
            generated_content=None,
            word_count=0,
            success=False,
            error_message=str(e),
            original_context=f"{request.title} - {request.context}"
        )


# @router.post("/generate-policy")
# async def generate_policy_content_legacy(request: PolicyGenerationRequest):
#     """
#     Legacy endpoint for backward compatibility.
#     Generates policy content and returns in the original format.
#     """
#     try:
#         result = await generate_policy_html(
#             title=request.title,
#             context=request.context,
#             target_words=request.target_words,
#             organization_type=request.organization_type
#         )
#         print("generate_policy_content---------\n:", result.get("generated_content"))
#         # Return in original format for backward compatibility
#         return {
#             "status": result.get("status", "success"),
#             "generated_content": result.get("generated_content"),
#             "word_count": result.get("word_count", 0),
#             "success": result.get("success", False),
#             "error_message": result.get("error_message"),
#             "original_context": result.get("original_context", "")
#         }
#     except Exception as e:
#         print(f"Route error: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         return {
#             "status": "error",
#             "generated_content": None,
#             "word_count": 0,
#             "success": False,
#             "error_message": str(e),
#             "original_context": f"{request.title} - {request.context}"
#         }


# @router.get("/health")
# async def health_check():
#     """Health check endpoint"""
#     return {"status": "healthy", "service": "Policy Generation API"}