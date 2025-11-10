from app.services.fetch_history import fetch_history_async
from fastapi.responses import JSONResponse
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def validate_input(question: str, organization: str, auth_token: str) -> bool:
    logger.info("🔐 Checking auth and tokens...")
        
    history_result = await fetch_history_async(auth_token, limit=1, offset=0)
    
    if not history_result.get("success", True):
        if history_result.get("error") == "Unauthorized":
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "error": "Unauthorized",
                    "message": "You are unauthorized to access this resource."
                }
            )
        else:
            error_code = history_result.get('status_code', 500)
            error_message = history_result.get('message', 'Failed to verify authentication')
            return JSONResponse(
                status_code=error_code,
                content={
                    "status": "error",
                    "message": error_message
                }
            )
        
    return True