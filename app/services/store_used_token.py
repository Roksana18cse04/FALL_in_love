import requests
from app.config import BACKEND_TOKEN_COUNT_URL


# save token count
def used_token_store(type, used_tokens, auth_token):
    try:
        header = {"Authorization": f"Bearer {auth_token}"}
        tokenCount_payload = {
            "type": type,
            "token": used_tokens
        }
        token_response = requests.post(BACKEND_TOKEN_COUNT_URL, json=tokenCount_payload, headers=header, timeout=10)
        
        if token_response.status_code == 201:
            print("saved used token successfully!")
        else:
            print(f"Token save failed - Status: {token_response.status_code}, Response: {token_response.text[:200]}")
            
        return token_response
    except Exception as e:
        print(f"Token store error: {str(e)}")
        return {"error": str(e), "status_code": 500}

if __name__=="__main__":
    used_token = 10
    type = 'chatbot'
    auth_token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzYwODUzMTU5LCJpYXQiOjE3NTgyNjExNTksImp0aSI6ImExM2ExOGI0YWIwNTRmMWI5NDUxMDVlYmZiMTE0NTRmIiwidXNlcl9pZCI6IjcifQ.iHJDqnwOyfJDNQbwF-3kI4fH4bif-37mIElm_ZC4hxA'

    res = used_token_store(type, used_token, auth_token)
    print(res)
