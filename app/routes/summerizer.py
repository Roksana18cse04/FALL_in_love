from fastapi import APIRouter, UploadFile, File
from app.services.summarize_pdf import summarize_with_gpt4
from app.services.extract_content import extract_content_from_pdf
from app.services.classification import classify_category
from app.services.store_used_token import used_token_store
from fastapi.responses import JSONResponse

router = APIRouter()

@router.post("/summary-with-category")
async def get_summary_and_category_endpoint(auth_token:str, file: UploadFile = File(...)):
    # Implement your summary logic here
    try:
        text, title = await extract_content_from_pdf(file)
        response = await summarize_with_gpt4(text, title)
        summary = response['summary']
        if not summary or summary.strip() == "":
            return {f"error": "Failed to generate summary from GPT-4: " + response['message']}
        summary_used_tokens = response['used_tokens']
   
        classify_response = await classify_category(docs_summary=summary)
        category = classify_response['category']
        if not category or category == "others":
            return {f"error": "Failed to classify category: " + classify_response.get('error', 'Unknown error')}
        
        # total used tokens
        total_used_tokens = summary_used_tokens + classify_response['used_tokens']

        # save summary used token
        token_response = used_token_store(type= 'summarization', used_tokens=total_used_tokens, auth_token=auth_token)
        if token_response.status_code != 201:
            return JSONResponse(status_code=500, content={
            "status": "error",
            "message": "Failed to save summarization used token.",
            
        })

        # upload to cloud storage
        # get url link

        return {
            "summary": summary,
            "category": category,
            # "url": url
            "used_tokens": total_used_tokens  
        }

    except Exception as e:
        return {"error": str(e)}