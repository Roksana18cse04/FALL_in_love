from app.config import OPENAI_API_KEY
from openai import OpenAI
import asyncio
import numpy as np

openai_client = OpenAI(api_key=OPENAI_API_KEY)

async def embed_text_openai(text: str) -> list:
    """
    Generate an embedding vector for the given text using OpenAI's embedding API.
    If the text is too long, split it into chunks, embed each, and average the embeddings.
    Returns a list of floats (embedding vector).
    """
    # Helper: split text into chunks of ~2000 tokens (safe for 8192 limit)
    def split_text(text, max_tokens=2000):
        words = text.split()
        chunks = []
        for i in range(0, len(words), max_tokens):
            chunk = ' '.join(words[i:i+max_tokens])
            chunks.append(chunk)
        return chunks

    chunks = split_text(text, max_tokens=2000)
    loop = asyncio.get_event_loop()
    def sync_embed_batch(texts):
        responses = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=texts
        )
        return [item.embedding for item in responses.data]
    embeddings = await loop.run_in_executor(None, sync_embed_batch, chunks)
    embedding_matrix = np.array(embeddings)
    avg_embedding = np.mean(embedding_matrix, axis=0)
    return avg_embedding.tolist()
