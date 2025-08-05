from datetime import datetime, timezone
from app.services.weaviate_client import client
from app.services.extract_content import extract_content_from_pdf
from app.services.dropbox_operation import upload_pdf_to_dropbox, delete_file
from fastapi.responses import JSONResponse


class_name = "PolicyDocuments" 

async def weaviate_insertion(file, category="aged care"):
    
    try:
        # for source: upload file to cloudinary
        res = await upload_pdf_to_dropbox(file, category)
        if res['status_code']==409:
            return JSONResponse(res)
        
        elif res.get('status_code') != 200:
            return JSONResponse(status_code=500, content={
                "status": "error",
                "message": res.get("message", "Unknown error during upload.")
            })

        print("dropbox response------------", res)
        
        # Extract content from PDF
        data, title = await extract_content_from_pdf(file)
        if data=="":
            # remove file from dropbox
            await delete_file(res['uploaded_to'])
            return "Error extracting PDF content"

        # Ensure the client is connected
        if not client.is_connected():
            client.connect()

        data_object = {
            "title": title,
            "summary": "",
            "category": category,
            "data": data,
            "source": res['link'],
            "created_at": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
            "last_updated": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        }

        client.collections.get(class_name).data.insert(data_object)
        print(f"Data inserted into class '{class_name}' successfully.")
        return JSONResponse(status_code=201, content={
            "status": "success",
            "message": f"Document '{title}' inserted successfully.",
            "weaviate_class": class_name,
            "dropbox_link": res['link']
        })
        
        
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e)
        })
    finally:
        client.close()
