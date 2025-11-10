import aiohttp
from app.config import BACKEND_HISTORY_URL
import asyncio
from typing import Dict, Optional

# Shared HTTP session for connection pooling
http_session: Optional[aiohttp.ClientSession] = None


async def get_http_session() -> aiohttp.ClientSession:
    """Get or create shared HTTP session"""
    global http_session
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession()
    return http_session

async def fetch_history_async(auth_token: str, limit: int = 10, offset: int = 0) -> Dict:
    """Fetch chat history with error handling"""
    header = {"Authorization": f"Bearer {auth_token}"}
    params = {"limit": limit, "offset": offset}
    
    session = await get_http_session()
    
    try:
        async with session.get(
            BACKEND_HISTORY_URL, 
            headers=header, 
            params=params, 
            timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            status = response.status
            
            if status == 200:
                data = await response.json()
                histories = data.get('data', {}).get('histories', [])
                last_10_histories = histories[-10:] 
                last_10_histories = sorted(last_10_histories, key=lambda x: x['created_at'])
                print("Fetched history data:------------------------\n", last_10_histories)  # Debug log
                return {
                    "success": True,
                    "remaining_tokens": data.get('data', {}).get('remaining_tokens', None),
                    "histories": last_10_histories
                }
            elif status == 401:
                return {
                    "success": False, 
                    "error": "Unauthorized", 
                    "message": "You are unauthorized to access this resource.",
                    "status_code": 401
                }
            else:
                error_message = f"Request failed with status {status}"
                try:
                    error_data = await response.json()
                    error_message = error_data.get('message', error_data.get('detail', error_message))
                except:
                    pass
                
                return {
                    "success": False,
                    "error": f"http_{status}",
                    "message": error_message,
                    "status_code": status
                }
    except asyncio.TimeoutError:
        return {
            "success": False,
            "error": "timeout",
            "message": "Request timed out",
            "status_code": 504
        }
    except aiohttp.ClientError as e:
        return {
            "success": False,
            "error": "connection_error",
            "message": "Failed to connect to server",
            "status_code": 503
        }
    except Exception as e:
        return {
            "success": False,
            "error": "unexpected_error",
            "message": f"Unexpected error: {str(e)}",
            "status_code": 500
        }
