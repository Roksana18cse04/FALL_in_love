from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.extract_content import extract_content_from_pdf
from app.services.weaviate_client import get_weaviate_client
from app.services.embedding_service import embed_text_openai
import numpy as np

router = APIRouter()

@router.post("/user/check-policy-alignment")
async def check_policy_alignment(file: UploadFile = File(...)):
    # Extract text from PDF
    text, title = await extract_content_from_pdf(file)
    if not text:
        raise HTTPException(status_code=400, detail="Could not extract text from PDF.")
    # Embed text
    embedding = await embed_text_openai(text)
    # Fetch all stored embeddings from Weaviate
    client = get_weaviate_client()
    collection = client.collections.get("PolicyEmbeddings")
    response = collection.query.fetch_objects(limit=1000)  # adjust limit as needed
    all_objs = response.objects
    if not all_objs:
        raise HTTPException(status_code=404, detail="No stored policy embeddings found.")
    # Compute cosine similarity with each stored embedding
    def cosine_similarity(a, b):
        a = np.array(a)
        b = np.array(b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    similarities = [cosine_similarity(embedding, obj.properties["embedding"]) for obj in all_objs]
    max_similarity = max(similarities)
    percent = round(max_similarity * 100, 2)
    return {"alignment_percent": percent, "most_similar_policy": all_objs[np.argmax(similarities)].properties["filename"]}
