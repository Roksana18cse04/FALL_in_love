import os
import weaviate
from weaviate.auth import AuthApiKey
from app.config import WEAVIATE_API_KEY, WEAVIATE_HOST, OPENAI_API_KEY

def get_weaviate_client():
    if not WEAVIATE_API_KEY:
        raise ValueError("❌ WEAVIATE_API_KEY is not set in environment/config.")
    if not WEAVIATE_HOST:
        raise ValueError("❌ WEAVIATE_HOST is not set in environment/config.")

    headers = {}
    if OPENAI_API_KEY:
        headers["X-OpenAI-Api-Key"] = OPENAI_API_KEY

    client = weaviate.connect_to_weaviate_cloud(
        cluster_url=f"https://{WEAVIATE_HOST}",
        auth_credentials=AuthApiKey(WEAVIATE_API_KEY),
        headers=headers if headers else None,
    )
    return client
