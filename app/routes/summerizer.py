from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.summarize_pdf import summarize_with_gpt4
from app.services.extract_content import extract_content_from_uploadpdf
from app.services.extract_plain_text_from_html import extract_plain_text
from app.services.classification import classify_category
from app.services.store_used_token import used_token_store
from app.services.s3_manager import S3Manager
from fastapi.responses import JSONResponse
import asyncio
from app.services.policy_comparison_service import combined_alignment_analysis
from app.config import GLOBAL_ORG

router = APIRouter()

s3_manager = S3Manager()

@router.post("/summary-with-category")
async def get_summary_and_category_endpoint(auth_token:str, organization_type: str, doc_title: str, html_text: str):
    # Implement your summary logic here
    try:
        # text, title = await extract_content_from_uploadpdf(file)
        text = await extract_plain_text(html_text)
        title = doc_title
        print("-----------successfully extracted content")
        
        # Run summary and alignment analysis in parallel
        summary_task = summarize_with_gpt4(text, title)
        alignment_task = combined_alignment_analysis(text, title, organization_type)
        
        response, result = await asyncio.gather(summary_task, alignment_task)
        print("------------successfully summarized document")
        summary = response['summary']
        if not summary or summary.strip() == "":
            return {f"error": "Failed to generate summary from GPT-4: " + response['message']}
        summary_used_tokens = response['used_tokens']
   
        classify_response = await classify_category(docs_summary=summary)
        category = classify_response['category']
        if not category or category == "others":
            return {f"error": "Failed to classify category: " + classify_response.get('error', 'Unknown error')}
        
        # Extract alignment tokens and clean result
        alignment_tokens = result.pop('tokens_used', 0)
        alignment_result = {k: v for k, v in result.items() if k != 'tokens_used'}
        
        # total used tokens
        total_used_tokens = summary_used_tokens + classify_response['used_tokens'] + alignment_tokens

        # save summary used token
        token_response = used_token_store(type= 'summarization', used_tokens=total_used_tokens, auth_token=auth_token)
        if token_response.status_code != 201:
            return JSONResponse(status_code=500, content={
            "status": "error",
            "message": "Failed to save summarization used token.",
            
        })

        return {
            "summary": summary,
            "category": category,
            "used_tokens": total_used_tokens,
            "alignment_result": alignment_result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error to Summerizing document: {str(e)}")