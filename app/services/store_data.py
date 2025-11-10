from app.config import BACKEND_HISTORY_URL, BACKEND_DOC_READ_COUNT_URL
from typing import List, Dict
from app.services.fetch_history import get_http_session
from app.services.store_used_token import used_token_store
import aiohttp
import asyncio


async def save_data_parallel(
    history_data: dict, 
    readcount_data: dict, 
    token_data: dict, 
    auth_token: str
) -> List[Dict]:
    """Save history, read count, and token data in parallel"""
    header = {"Authorization": f"Bearer {auth_token}"}
    session = await get_http_session()
    
    async def post_with_error_handling(url: str, data: dict, request_type: str) -> Dict:
        try:
            async with session.post(
                url, 
                json=data, 
                headers=header,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                status = response.status
                
                if status in [200, 201]:
                    return {"type": request_type, "status": status, "success": True}
                else:
                    error_msg = f"Failed with status {status}"
                    try:
                        error_data = await response.json()
                        error_msg = error_data.get('message', error_data.get('detail', error_msg))
                    except:
                        pass
                    
                    return {
                        "type": request_type,
                        "status": status,
                        "success": False,
                        "error": error_msg
                    }
        except Exception as e:
            return {
                "type": request_type,
                "status": 503,
                "success": False,
                "error": str(e)
            }
    
    async def post_history():
        return await post_with_error_handling(BACKEND_HISTORY_URL, history_data, "history")
    
    async def post_readcount():
        if not readcount_data:
            return {"type": "readcount", "status": 200, "skipped": True, "success": True}
        return await post_with_error_handling(BACKEND_DOC_READ_COUNT_URL, readcount_data, "readcount")
    
    async def post_token():
        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None, 
                lambda: used_token_store(
                    type='chatbot', 
                    used_tokens=token_data['used_tokens'], 
                    auth_token=auth_token
                )
            )
            
            status = resp.status_code if hasattr(resp, 'status_code') else 200
            if status in [200, 201]:
                return {"type": "token", "status": status, "success": True}
            else:
                return {
                    "type": "token",
                    "status": status,
                    "success": False,
                    "error": f"Failed with status {status}"
                }
        except Exception as e:
            return {
                "type": "token",
                "status": 500,
                "success": False,
                "error": str(e)
            }
    
    results = await asyncio.gather(
        post_history(),
        post_readcount(),
        post_token(),
        return_exceptions=True
    )
    
    return results