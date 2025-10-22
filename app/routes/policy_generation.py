from fastapi import APIRouter
from pydantic import BaseModel
from app.services.policy_llm import generate_policy_html

router = APIRouter(prefix="/policy", tags=["Policy Generation"])

class PolicyGenerationRequest(BaseModel):
    title: str
    context: str
    target_words: int = 3000

class PolicyGenerationResponse(BaseModel):
    generated_content: str
    word_count: int
    success: bool
    error_message: str = None
    original_context: str

@router.post("/generate-html", response_model=PolicyGenerationResponse)
async def generate_policy_content(request: PolicyGenerationRequest):
    """
    Generate policy content in HTML format with professional styling.
    Returns HTML-formatted content for rich text display.
    
    Args:
        request: PolicyGenerationRequest containing title, context, and target word count
        
    Returns:
        PolicyGenerationResponse with HTML-formatted content, word count, and success status
    """
    result = await generate_policy_html(
        title=request.title,
        context=request.context,
        target_words=request.target_words
    )
    
    return PolicyGenerationResponse(
        generated_content=result["generated_content"],
        word_count=result["word_count"],
        success=result["success"],
        error_message=result["error_message"],
        original_context=result["original_context"]
    )