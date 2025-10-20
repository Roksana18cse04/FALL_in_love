from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.summarize_pdf import summarize_with_gpt4
from app.services.extract_content import extract_content_from_uploadpdf
from app.services.classification import classify_category
from app.services.store_used_token import used_token_store
from app.services.s3_manager import S3Manager
from fastapi.responses import JSONResponse

router = APIRouter()

s3_manager = S3Manager()

@router.post("/summary-with-category")
async def get_summary_and_category_endpoint(auth_token:str, type: str, file: UploadFile = File(...)):
    # Implement your summary logic here
    try:
        text, title = await extract_content_from_uploadpdf(file)
        print("-----------successfully extracted content")
        response = await summarize_with_gpt4(text, title)
        print("------------successfully summarized document")
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

        # # upload to cloud storage
        # upload_response = s3_manager.upload_document(file, category, type)
        # if upload_response:
        #     return {
        #         "summary": summary,
        #         "category": category,
        #         "used_tokens": total_used_tokens,
        #         "aws_object_key": upload_response['object_key'],
        #         "aws_version_id": upload_response['version_id'] 
        #     }
        # else:
        #     print('File Uploaded Failed')
        #     return JSONResponse(status_code=500, content={
        #         "status": "error",
        #         "message": "File upload failed."
        #     })

        return {
            "summary": summary,
            "category": category,
            "used_tokens": total_used_tokens
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error to Summerizing document: {str(e)}")