from datetime import datetime, timezone
import json
from app.services.weaviate_client import get_weaviate_client
from app.services.extract_content import extract_content_from_pdf
from app.services.s3_manager import S3Manager
from fastapi.responses import JSONResponse
from uuid import uuid5, NAMESPACE_URL
import os
from weaviate.classes.query import Filter
from app.services.extract_plain_text_from_html import extract_plain_text

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


async def delete_existing_document_by_id_and_version(client, collection_name, doc_db_id, version_id):
    """Delete existing document chunks with the same document_id and version_id"""
    collection = client.collections.get(collection_name)
    
    # Find existing documents with same document_id and version_id
    results = collection.query.fetch_objects(
        filters=Filter.by_property("document_id").equal(str(doc_db_id)) & 
                Filter.by_property("version_id").equal(str(version_id))
    )
    
    # Delete existing chunks
    for obj in results.objects:
        collection.data.delete_by_id(obj.uuid)
    
    return len(results.objects)

from app.services.schema_manager import create_schema
async def weaviate_insertion(organization, doc_db_id, document_type, content, category, title, version_id, version_number):
    client = get_weaviate_client()
    try:
        # Ensure schema exists
        await create_schema(organization)

        data = await extract_plain_text(content)
        chunks = chunk_text(data)
        print(f"Document split into {len(chunks)} chunks.")
        
        # Check and delete existing document with same document_id and version_id
        if not client.is_connected():
            client.connect()
        deleted_count = await delete_existing_document_by_id_and_version(client, organization, doc_db_id, version_id)
        if deleted_count > 0:
            print(f"Updated existing document ID '{doc_db_id}' version '{version_id}' to title '{title}' (deleted {deleted_count} old chunks)")
            action = "updated"
        else:
            print(f"Inserting new document '{title}' with ID '{doc_db_id}' version '{version_id}'")
            action = "inserted"

        # Insert new chunks
        for idx, chunk in enumerate(chunks):
            try:
                collection = client.collections.get(organization)
                collection.data.insert(
                    properties={
                        "document_id": str(doc_db_id),
                        "document_type": document_type,
                        "title": title,
                        "category": category,
                        "version_id": version_id,
                        "version_number": version_number,
                        "data": chunk,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "last_updated": datetime.now(timezone.utc).isoformat()
                    }
                )
            except Exception as e:
                raise e

        return JSONResponse(
            status_code=201,
            content={
                "status": "success",
                "message": f"Document '{title}' {action} successfully with version {version_number}."
            }
        )
    
    except Exception as e:
        raise e

    finally:
        client.close()

