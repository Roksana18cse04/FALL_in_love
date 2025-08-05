import dropbox
from app.config import DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_REFRESH_TOKEN
import requests

async def upload_pdf_to_dropbox(file, category):
    
    dbx = dropbox.Dropbox(
        app_key=DROPBOX_APP_KEY,
        app_secret=DROPBOX_APP_SECRET,
        oauth2_refresh_token=DROPBOX_REFRESH_TOKEN
    )

    dropbox_path = f"/app/{category}/{file.filename}"

    try:
        # Check existence
        dbx.files_get_metadata(dropbox_path)
        return {"status_code": 409, "message": "File already exists"}
    except:
        # File doesn't exist, upload it
        contents = await file.read()
        
        # Ensure folder exists
        try:
            dbx.files_create_folder_v2(f"/app/{category}")
        except:
            pass
            
        # Upload and create link
        dbx.files_upload(contents, dropbox_path, mode=dropbox.files.WriteMode.add)
        shared_link = dbx.sharing_create_shared_link_with_settings(dropbox_path).url
        
        return {
            "status_code": 200,
            "uploaded_to": dropbox_path,
            "link": shared_link
        }

async def delete_file(dropbox_path):
    dbx = dropbox.Dropbox(
        app_key=DROPBOX_APP_KEY,
        app_secret=DROPBOX_APP_SECRET,
        oauth2_refresh_token=DROPBOX_REFRESH_TOKEN
    )
    dbx.files_delete_v2(dropbox_path)
    print(f"remove file successfully from {dropbox_path}")
