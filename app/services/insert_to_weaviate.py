from datetime import datetime, timezone
from app.services.weaviate_client import client
from app.services.extract_content import extract_content_from_pdf
from app.services.dropbox_operation import upload_pdf_to_dropbox, delete_file
from app.services.summarize_pdf import summarize_with_gpt4
from fastapi.responses import JSONResponse
from uuid import uuid5, NAMESPACE_URL

def chunk_text(text, max_chars=7000):
    """Split text into chunks without cutting sentences mid-way."""
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) <= max_chars:
            current_chunk += sentence + " "
        else:
            chunks.append(current_chunk.strip())
            current_chunk = sentence + " "
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

async def weaviate_insertion(organization, file, category="aged care"):
    
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

         # 🔁 FIX: Rewind file stream before extracting content
        file.file.seek(0)
        
        # Extract content from PDF
        data, title = await extract_content_from_pdf(file)
        if data=="":
            # remove file from dropbox
            await delete_file(res['uploaded_to'])
            return "Error extracting PDF content"
        summary = await summarize_with_gpt4(data,title)
        print("summary created successfully------------------")

        # Ensure the client is connected
        if not client.is_connected():
            client.connect()  
    
         # Get collection
        try:
            collection = client.collections.get(organization)
        except Exception:
            return JSONResponse(status_code=404, content={
                "status": "error",
                "message": f"Collection '{organization}' not found in Weaviate."
            })

        # Split document text into chunks
        chunks = chunk_text(data)

        
        document_id = uuid5(NAMESPACE_URL, res['link'])

        # Insert chunks
        for idx, chunk in enumerate(chunks):
            chunk_uuid = uuid5(document_id, f"chunk-{idx}")
            collection.data.insert(
                properties={
                    "title": title,
                    "summary": summary,
                    "category": category,
                    "data": chunk,
                    "source": res['link'],
                    "created_at": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
                    "last_updated": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
                },
                uuid=str(chunk_uuid)
            )
        print(f"Data inserted into class '{organization}' successfully.")
        return JSONResponse(status_code=201, content={
            "status": "success",
            "message": f"Document '{title}' inserted successfully.",
            "weaviate_class": organization,
            "source": res['link']
        })
        
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e)
        })
    finally:
        client.close()
