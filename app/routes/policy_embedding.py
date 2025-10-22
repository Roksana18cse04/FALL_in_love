from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import PlainTextResponse
from weaviate.classes.query import Filter
from app.services.extract_content import extract_content_from_uploadpdf
from app.services.law_deletion import delete_weaviate_law
from app.services.weaviate_client import get_weaviate_client
from app.services.embedding_service import embed_text_openai
import uuid
import re
import tiktoken

router = APIRouter()

def get_version_from_filename(filename: str) -> str:
    """Extract version from filename like 'policy_v2.pdf' -> 'v2'. Defaults to 'v1'."""
    match = re.search(r"_v(\d+)", filename or "")
    if match:
        return f"v{match.group(1)}"
    return "v1"

def chunk_text_by_tokens(text: str, max_tokens: int = 7000) -> list[str]:
    """Split text into chunks based on token count using tiktoken."""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")  # OpenAI's encoding
        tokens = encoding.encode(text)
        
        chunks = []
        for i in range(0, len(tokens), max_tokens):
            chunk_tokens = tokens[i:i + max_tokens]
            chunks.append(encoding.decode(chunk_tokens))
        
        return chunks
    except Exception as e:
        # Fallback to simple word-based chunking if tiktoken fails
        print(f"Tiktoken failed, using fallback chunking: {e}")
        return chunk_text_simple(text, max_tokens)

def chunk_text_simple(text: str, max_tokens: int = 7000) -> list[str]:
    """Fallback: Simple word-based chunking (approximate)."""
    # Rough estimation: 1 token ≈ 4 characters
    max_chars = max_tokens * 4
    chunks = []
    
    words = text.split()
    current_chunk = []
    current_length = 0
    
    for word in words:
        word_length = len(word) + 1  # +1 for space
        
        if current_length + word_length > max_chars and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_length = word_length
        else:
            current_chunk.append(word)
            current_length += word_length
    
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    return chunks

def compute_next_version(collection, title: str) -> str:
    """Return the next version for a given title by inspecting existing objects."""
    try:
        results = collection.query.fetch_objects(
            where={
                "path": ["title"],
                "operator": "Equal",
                "valueText": title,
            }
        )
        versions = []
        for obj in getattr(results, "objects", []) or []:
            v = (obj.properties or {}).get("version", "v1")
            try:
                if isinstance(v, str) and v.startswith("v"):
                    versions.append(int(v[1:]))
                else:
                    versions.append(int(v))
            except Exception:
                versions.append(1)
        if not versions:
            return "v1"
        return f"v{max(versions) + 1}"
    except Exception:
        # Fallback if query fails
        return "v1"

def compute_global_next_version(collection) -> str:
    """Return next version number irrespective of title/filename.

    Looks at all objects in the collection, finds the highest version value,
    and returns v{max+1}. If no objects or version missing, starts at v1.
    """
    try:
        results = collection.query.fetch_objects()
        max_version = 0
        for obj in getattr(results, "objects", []) or []:
            v = (obj.properties or {}).get("version")
            if not v:
                continue
            try:
                if isinstance(v, str) and v.startswith("v"):
                    max_version = max(max_version, int(v[1:]))
                else:
                    max_version = max(max_version, int(v))
            except Exception:
                continue
        return f"v{max_version + 1 if max_version > 0 else 1}"
    except Exception:
        return "v1"

@router.post("/admin/upload-law")
async def upload_law_pdf(law_type: str, file: UploadFile = File(...)):
    client = None
    try:
        # Extract text from PDF
        text, title = await extract_content_from_uploadpdf(file)
        print("text----------", text[:500])

        if not text:
            raise HTTPException(status_code=400, detail="Could not extract text from PDF.")

        # ✅ Split text into chunks to avoid token limit
        chunks = chunk_text_by_tokens(text, max_tokens=7000)
        print(f"Text split into {len(chunks)} chunks")

        # Connect to Weaviate (REST-safe connection)
        client = get_weaviate_client()

        # ✅ Check if collection exists
        collections = client.collections.list_all()

        if law_type not in collections:
            from weaviate.classes.config import Property, DataType, Configure, VectorDistances

            client.collections.create(
                name=law_type,
                vectorizer_config=Configure.Vectorizer.text2vec_openai(
                    model="text-embedding-3-small",
                    vectorize_collection_name=False
                ),
                vector_index_config=Configure.VectorIndex.hnsw(
                    distance_metric=VectorDistances.COSINE,
                    ef_construction=128,
                    max_connections=64
                ),
                properties=[
                    Property(name="law_id", data_type=DataType.TEXT),
                    Property(name="title", data_type=DataType.TEXT),
                    Property(name="text", data_type=DataType.TEXT),
                    Property(name="version", data_type=DataType.TEXT),
                    Property(name="chunk_index", data_type=DataType.NUMBER),  # ✅ Track chunk position
                    Property(name="total_chunks", data_type=DataType.NUMBER),  # ✅ Total chunks for this document
                    Property(name="embedding", data_type=DataType.NUMBER_ARRAY),
                ],
            )

        collection = client.collections.get(law_type)
        
        # Get next version for this title
        next_version = compute_next_version(collection, title)

        # ✅ Insert each chunk separately
        inserted_chunks = []
        for i, chunk in enumerate(chunks):
            try:
                # Embed each chunk
                embedding = await embed_text_openai(chunk)
                
                # Create unique law_id for each chunk
                chunk_law_id = str(uuid.uuid4())
                
                # Insert chunk with metadata
                collection.data.insert({
                    "law_id": chunk_law_id,
                    "title": title,  # Keep original title
                    "text": chunk,
                    "version": next_version,
                    "chunk_index": i + 1,  # 1-indexed for readability
                    "total_chunks": len(chunks),
                    "embedding": embedding
                })
                
                inserted_chunks.append({
                    "chunk_index": i + 1,
                    "law_id": chunk_law_id,
                    "char_count": len(chunk)
                })
                
                print(f"✅ Inserted chunk {i+1}/{len(chunks)} - {len(chunk)} chars")
                
            except Exception as chunk_error:
                print(f"❌ Failed to insert chunk {i+1}: {str(chunk_error)}")
                # Continue with other chunks even if one fails
                continue

        if not inserted_chunks:
            raise HTTPException(status_code=500, detail="Failed to insert any chunks")

        return {
            "status": "success",
            "title": title,
            "version": next_version,
            "total_chunks": len(chunks),
            "inserted_chunks": len(inserted_chunks),
            "chunks_info": inserted_chunks
        }
        
    except Exception as e:
        print(f"❌ Upload failed: {str(e)}")
        return {"status": "failed", "message": str(e)}
    
    finally:
        if client:
            client.close()


from pydantic import BaseModel

class PolicyDeletionRequest(BaseModel):
    version: str
    filename: str

@router.get("/admin/delete-law")
async def delete_law(request: PolicyDeletionRequest):
    response = await delete_weaviate_law(request.version, request.filename)
    return response