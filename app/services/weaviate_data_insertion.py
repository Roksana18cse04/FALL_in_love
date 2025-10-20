from datetime import datetime, timezone
import json
from app.services.weaviate_client import get_weaviate_client
from app.services.extract_content import extract_content_from_pdf
from app.services.s3_manager import S3Manager
from fastapi.responses import JSONResponse
from uuid import uuid5, NAMESPACE_URL
import os
from weaviate.classes.query import Filter

s3 = S3Manager()

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


async def get_next_version(client, collection_name, title):
    """Get the next version number for a document with the given title"""
    collection = client.collections.get(collection_name)
    
    # Query for existing documents with the same title
    results = collection.query.fetch_objects(
        filters=Filter.by_property("title").equal(title)
    )
    
    versions = []
    for obj in results.objects:
        v = obj.properties.get("version", "v1")
        # Extract numeric part from version (e.g., "v2" -> 2)
        try:
            if v.startswith("v"):
                versions.append(int(v[1:]))
            else:
                versions.append(int(v))
        except (ValueError, TypeError):
            versions.append(1)
    
    if not versions:
        return "v1"
    
    print("all version version ---------", versions)
    next_version = max(versions) + 1
    print("next version -------------", next_version)
    return f"v{next_version}"


async def weaviate_insertion(organization, doc_db_id, document_type, document_object_key, category):
    client = get_weaviate_client()
    try:
        temp_file_path = s3.download_document(document_object_key)
        if not temp_file_path:
            return JSONResponse(status_code=404, content={
                "status": "error",
                "message": "Failed to download file"
            })

        data, title = await extract_content_from_pdf(temp_file_path)
        chunks = chunk_text(data)
        version = await get_next_version(client, organization, title)
        document_id = uuid5(NAMESPACE_URL, f"{document_object_key}-{version}")

        # Insert chunks
        for idx, chunk in enumerate(chunks):
            chunk_uuid = uuid5(document_id, f"chunk-{idx}")
            try:
                collection = client.collections.get(organization)
                collection.data.insert(
                    properties={
                        "document_id": str(doc_db_id),
                        "document_type": document_type,
                        "title": title,
                        "category": category,
                        "source": document_object_key,
                        "version": version,
                        "data": chunk,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "last_updated": datetime.now(timezone.utc).isoformat()
                    },
                    uuid=str(chunk_uuid)
                )
            except Exception as e:
                raise e

        os.remove(temp_file_path)
        return JSONResponse(
            status_code=201,
            content={
                "status": "success",
                "message": f"Document '{title}' inserted successfully with version {version}."
            }
        )
    
    except Exception as e:
        raise e

    finally:
        client.close()







# from datetime import datetime, timezone
# from app.services.weaviate_client import get_weaviate_client
# from app.services.extract_content import extract_content_from_pdf
# from app.services.dropbox_operation import upload_pdf_to_dropbox, delete_file
# from app.services.summarize_pdf import summarize_with_gpt4
# from fastapi.responses import JSONResponse
# from uuid import uuid5, NAMESPACE_URL
# import pdfplumber
# import io
# from fastapi import APIRouter, Query

# def chunk_text(text, max_chars=7000):
#     """Split text into chunks without cutting sentences mid-way."""
#     import re
#     sentences = re.split(r'(?<=[.!?])\s+', text)
#     chunks = []
#     current_chunk = ""

#     for sentence in sentences:
#         if len(current_chunk) + len(sentence) <= max_chars:
#             current_chunk += sentence + " "
#         else:
#             chunks.append(current_chunk.strip())
#             current_chunk = sentence + " "
#     if current_chunk:
#         chunks.append(current_chunk.strip())
#     return chunks

# # Version-aware PDF extraction
# def get_version_from_filename(filename: str) -> str:
#     """Extract version from filename like 'policy_v2.pdf' -> 'v2'"""
#     import re
#     match = re.search(r'_v(\d+)', filename)
#     if match:
#         return f"v{match.group(1)}"
#     return "v1"

# async def extract_pdf_content_with_version(file, version=None):
#     """Extract content from PDF with version handling"""
#     try:
#         contents = await file.read()
#         pdf_bytes = io.BytesIO(contents)
#         text = ""
#         with pdfplumber.open(pdf_bytes) as pdf:
#             for page in pdf.pages:
#                 page_text = page.extract_text()
#                 if page_text:
#                     text += page_text + "\n"
#         title = file.filename.replace(".pdf", "") if file.filename else "Unknown Document"
#         version = version or get_version_from_filename(file.filename or "")
#         return text.strip(), title, version
#     except Exception as e:
#         print(f"Error extracting PDF content: {str(e)}")
#         title = file.filename.replace(".pdf", "") if file.filename else "Unknown Document"
#         version = version or get_version_from_filename(file.filename or "")
#         return "", title, version

# router = APIRouter()

# def ensure_version_field(client, collection_name):
#     """Ensure version field exists in the specified collection"""
#     try:
#         collection = client.collections.get(collection_name)
#         schema = collection.schema.get()
        
#         # Check if version field already exists
#         if not any(p["name"] == "version" for p in schema["properties"]):
#             collection.schema.add_property({
#                 "name": "version",
#                 "dataType": ["text"],
#                 "description": "Version of the document"
#             })
#             print(f"Added version field to collection '{collection_name}'")
#         else:
#             print(f"Version field already exists in collection '{collection_name}'")
#     except Exception as e:
#         print(f"Error ensuring version field: {str(e)}")

# def get_next_version(client, collection_name, title):
#     """Get the next version number for a document with the given title"""
#     try:
#         collection = client.collections.get(collection_name)
        
#         # Query for existing documents with the same title
#         results = collection.query.fetch_objects(
#             where={
#                 "path": ["title"],
#                 "operator": "Equal",
#                 "valueText": title
#             }
#         )
        
#         versions = []
#         for obj in results.objects:
#             v = obj.properties.get("version", "v1")
#             # Extract numeric part from version (e.g., "v2" -> 2)
#             try:
#                 if v.startswith("v"):
#                     versions.append(int(v[1:]))
#                 else:
#                     versions.append(int(v))
#             except (ValueError, TypeError):
#                 versions.append(1)
        
#         if not versions:
#             return "v1"
        
#         next_version = max(versions) + 1
#         return f"v{next_version}"
        
#     except Exception as e:
#         print(f"Error getting next version: {str(e)}")
#         return "v1"

# # FastAPI router for versioned GET
# @router.get("/policy/version")
# async def get_policy_by_version(collection_name: str, version: str = Query(...)):
#     client = get_weaviate_client()
#     try:
#         collection = client.collections.get(collection_name)
#         results = collection.query.fetch_objects(
#             where={
#                 "path": ["version"],
#                 "operator": "Equal",
#                 "valueText": version
#             }
#         )
#         return {"policies": [obj.properties for obj in results.objects]}
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"error": str(e)})
#     finally:
#         client.close()

# @router.get("/policy/latest")
# async def get_latest_policies(collection_name: str):
#     client = get_weaviate_client()
#     try:
#         collection = client.collections.get(collection_name)
#         results = collection.query.fetch_objects()
        
#         # Group by title and pick the highest version for each
#         from collections import defaultdict
#         grouped = defaultdict(list)
#         for obj in results.objects:
#             title = obj.properties.get("title", "")
#             grouped[title].append(obj)
        
#         latest_policies = []
#         for title, objs in grouped.items():
#             def version_key(obj):
#                 v = obj.properties.get("version", "v1")
#                 try:
#                     if v.startswith("v"):
#                         return int(v[1:])
#                     return int(v)
#                 except (ValueError, TypeError):
#                     return 1
            
#             latest = max(objs, key=version_key)
#             latest_policies.append(latest.properties)
        
#         return {"policies": latest_policies}
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"error": str(e)})
#     finally:
#         client.close()

# async def weaviate_insertion(organization, file, category="aged care"):
#     client = get_weaviate_client()
#     try:
#         # Upload file to dropbox
#         res = await upload_pdf_to_dropbox(file, category)
#         if res['status_code'] == 409:
#             return JSONResponse(res)
#         elif res.get('status_code') != 200:
#             return JSONResponse(status_code=500, content={
#                 "status": "error",
#                 "message": res.get("message", "Unknown error during upload.")
#             })

#         print("dropbox response------------", res)

#         # Rewind file stream before extracting content
#         file.file.seek(0)
        
#         # Extract content from PDF with version
#         data, title, version = await extract_pdf_content_with_version(file)
#         if data == "":
#             # Remove file from dropbox
#             await delete_file(res['uploaded_to'])
#             return "Error extracting PDF content"
        
#         summary = await summarize_with_gpt4(data, title)
#         print("summary created successfully------------------")

#         # Ensure the client is connected
#         if not client.is_connected():
#             client.connect()  
    
#         # Get collection
#         try:
#             collection = client.collections.get(organization)
#         except Exception:
#             return JSONResponse(status_code=404, content={
#                 "status": "error",
#                 "message": f"Collection '{organization}' not found in Weaviate."
#             })

#         # Ensure version field exists in the collection
#         ensure_version_field(client, organization)
        
#         # Get the next version for this document title
#         document_version = get_next_version(client, organization, title)
#         print(f"Assigning version {document_version} to document '{title}'")

#         # Split document text into chunks
#         chunks = chunk_text(data)
        
#         document_id = uuid5(NAMESPACE_URL, res['link'])

#         # Insert chunks with version information
#         for idx, chunk in enumerate(chunks):
#             chunk_uuid = uuid5(document_id, f"chunk-{idx}")
#             collection.data.insert(
#                 properties={
#                     "title": title,
#                     "summary": summary,
#                     "category": category,
#                     "data": chunk,
#                     "source": res['link'],
#                     "version": document_version,  # ✅ NOW INCLUDING VERSION
#                     "created_at": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
#                     "last_updated": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
#                 },
#                 uuid=str(chunk_uuid)
#             )
        
#         print(f"Data inserted into class '{organization}' successfully with version {document_version}.")
#         return JSONResponse(status_code=201, content={
#             "status": "success",
#             "message": f"Document '{title}' inserted successfully with version {document_version}.",
#             "weaviate_class": organization,
#             "source": res['link'],
#             "version": document_version
#         })
        
#     except Exception as e:
#         print(f"Error in weaviate_insertion: {str(e)}")
#         return JSONResponse(status_code=500, content={
#             "status": "error",
#             "message": str(e)
#         })
#     finally:
#         client.close()