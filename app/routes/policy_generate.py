from fastapi import APIRouter, Response, HTTPException
from pydantic import BaseModel, Field
import asyncio
from app.services.store_used_token import used_token_store
from app.services.policy_llm import generate_policy_html
from app.utils._clean_html import advanced_html_cleaner

router = APIRouter()

class PolicyGenerationRequest(BaseModel):
    auth_token: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=200)
    context: str = Field(..., min_length=10)
    organization_type: str = Field(..., min_length=1)
    target_words: int = Field(default=3000, ge=500, le=10000)

@router.post("/generate-html")
async def generate_html(request: PolicyGenerationRequest):
    """
    Generate policy HTML with optimized performance and error handling
    """
    try:
        # Run policy generation with timeout
        result = await asyncio.wait_for(
            generate_policy_html(
                title=request.title,
                context=request.context,
                organization_type=request.organization_type,
                target_words=request.target_words
            ),
            timeout=120.0  # 2 minute timeout
        )
        
        generated_content = result.get("generated_content")
        if not generated_content:
            raise HTTPException(status_code=500, detail="No content generated")
        
        used_tokens = result.get("used_tokens", 0)
        
        # Save token usage (fire and forget)
        asyncio.create_task(
            asyncio.to_thread(
                used_token_store,
                type='policy_generation',
                used_tokens=used_tokens,
                auth_token=request.auth_token
            )
        )
        
        # Clean HTML content
        clean_html_content = advanced_html_cleaner(generated_content)
        
        return Response(
            content=clean_html_content,
            media_type="text/html; charset=utf-8",
            headers={
                "X-Words": str(result.get("word_count", 0)),
                "X-Success": "True",
                "X-Tokens-Used": str(used_tokens),
                "Cache-Control": "no-cache"
            }
        )
        
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Request timeout")
    except Exception as e:
        return Response(
            content=f"<h1>Generation Error</h1><p>{str(e)}</p>",
            media_type="text/html",
            status_code=500,
            headers={
                "X-Success": "False",
                "X-Error": str(e)[:100]  # Limit error message length
            }
        )