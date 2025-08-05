from app.config import DROPBOX_APP_KEY, DROPBOX_APP_SECRET
import requests


def get_refresh_token(code):
    url = "https://api.dropboxapi.com/oauth2/token"
    data = {
        "code": code,
        "grant_type": "authorization_code",
        "client_id": DROPBOX_APP_KEY,
        "client_secret": DROPBOX_APP_SECRET,
        "redirect_uri": "http://127.0.0.1:8000/oauth2/callback"
    }
    response = requests.post(url, data=data)
    res_json = response.json()
    print("response------------", res_json)
    
    refresh_token = res_json.get("refresh_token")
    if not refresh_token:
        print("did not get reference token")
    return refresh_token

if __name__=="__main__":
    refresh_token = get_refresh_token("RXHYCKRArdIAAAAAAAAAKi3C24xTFwN_m0WO7ktmNz4") # code works only one times.
    print("refresh token -------------", refresh_token)