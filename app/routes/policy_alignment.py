from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.policy_comparison_service import cosine_similarity_test, summarize_pdf_and_policies, combined_alignment_analysis
import logging
from app.services.extract_plain_text_from_html import extract_plain_text

router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@router.post("/user/check-policy-alignment")
async def check_policy_alignment(title: str, html_text: str, organization_type: str = "General"):
    """Policy alignment analysis with specific law type comparison."""
    logger.info(f"Processing text for {organization_type} law alignment")
    text = await extract_plain_text(html_text)
    try:
        result = await combined_alignment_analysis(text, title, organization_type)
        logger.info(f"Law alignment analysis completed for {title}")
        return result
        
    except Exception as e:
        logger.error(f"Policy alignment analysis failed for {title}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# @router.post("/user/summarize-pdf-and-policies")
# async def summarize_pdf_and_weaviate_policies(file: UploadFile = File(...)):
#     """
#     Fetch Weaviate policy texts and return brief summaries; extract full PDF text and return a brief summary.
#     """
#     try:
#         result = await summarize_pdf_and_policies(file, "PolicyEmbeddings")
#         return result
#     except Exception as e:
#         logger.error(f"Summarization failed for {file.filename}: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")
