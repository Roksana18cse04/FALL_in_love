from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.extract_content import extract_content_from_pdf
from app.services.weaviate_client import get_weaviate_client
from app.services.embedding_service import embed_text_openai
import uuid

router = APIRouter()

@router.post("/admin/upload-policy-pdf")
async def upload_policy_pdf(file: UploadFile = File(...)):
    # Extract text from PDF
    text, title = await extract_content_from_pdf(file)
    if not text:
        raise HTTPException(status_code=400, detail="Could not extract text from PDF.")
    # Embed text
    embedding = await embed_text_openai(text)
    # Save to Weaviate
    client = get_weaviate_client()
    # Check if collection exists, create if not
    collections = client.collections.list_all()
    if "PolicyEmbeddings" not in collections:
        from weaviate.classes.config import Property, DataType, Configure, VectorDistances, Tokenization
        client.collections.create(
            name="PolicyEmbeddings",
            vectorizer_config=Configure.Vectorizer.none(),
            vector_index_config=Configure.VectorIndex.hnsw(
                distance_metric=VectorDistances.COSINE,
                ef_construction=128,
                max_connections=64
            ),
            properties=[
                Property(name="policy_id", data_type=DataType.TEXT),
                Property(name="filename", data_type=DataType.TEXT),
                Property(name="title", data_type=DataType.TEXT),
                Property(name="text", data_type=DataType.TEXT),
                Property(name="embedding", data_type=DataType.NUMBER_ARRAY)
            ]
        )
    collection = client.collections.get("PolicyEmbeddings")
    obj_id = str(uuid.uuid4())
    collection.data.insert({
        "policy_id": obj_id,
        "filename": file.filename,
        "title": title,
        "text": text,
        "embedding": embedding
    }, vector=embedding)
    return {"status": "success", "policy_id": obj_id}
