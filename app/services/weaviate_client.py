import weaviate
from app.config import WEAVIATE_API_KEY, WEAVIATE_HOST, OPENAI_API_KEY
from weaviate.auth import _APIKey

client = weaviate.connect_to_weaviate_cloud(
    cluster_url=f"https://{WEAVIATE_HOST}",
    auth_credentials=_APIKey(WEAVIATE_API_KEY),
    headers={
        "X-OpenAI-Api-Key": OPENAI_API_KEY
    }
)
try:
    # Your code using client, e.g.:
    if client.is_ready():
        print("Weaviate client is connected and ready.")
    # other queries...
finally:
    client.close()  # Make sure to close connection when done