from datetime import datetime, timezone
import json
from app.services.weaviate_client import client
from app.services.extract_content import extract_content_from_url
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

async def weaviate_insertion(organization, doc_db_id, document_type, document_url, summary, category="aged care"):
    
    try:
        # Extract content from URL
        data, title = await extract_content_from_url(document_url)

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

        
        document_id = uuid5(NAMESPACE_URL, document_url)

        # Insert chunks
        for idx, chunk in enumerate(chunks):
            chunk_uuid = uuid5(document_id, f"chunk-{idx}")
            collection.data.insert(
                properties={
                    "document_id": str(doc_db_id),
                    "document_type": document_type,
                    "title": title,
                    "summary": summary,
                    "category": category,
                    "source": document_url,
                    "data": chunk,
                    "created_at": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
                    "last_updated": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
                },
                uuid=str(chunk_uuid)
            )
        print(f"Data inserted into class '{organization}' successfully.")
        return JSONResponse(status_code=201, content={
            "status": "success",
            "message": f"Document '{title}' inserted successfully.",
            "organization": organization,
            "source": document_url,
            "document_id": str(doc_db_id)
        })
        
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e)
        })
    finally:
        client.close()

if __name__ == "__main__":
    import asyncio
    response = asyncio.run(weaviate_insertion(
        organization="HomeCare",
        doc_db_id=123,
        document_type="Policy Document",
        document_url="https://www.dropbox.com/scl/fi/i4js5sapbbihzkbejonzy/provider-registration-policy.pdf?rlkey=2egqmz4na3g5v44w3976lpgo2&st=vicm51sf&dl=1",
        summary="This is a sample summary of the policy document.",
        category="Aged Care"
    ))
    from starlette.responses import JSONResponse
    print(json.loads(response.body))