import dropbox
from app.config import DROPBOX_API_KEY

async def upload_pdf_to_dropbox(file, category):

    dbx = dropbox.Dropbox(DROPBOX_API_KEY)
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
