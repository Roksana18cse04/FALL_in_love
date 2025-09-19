from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.routes.chatbot import router as chatbot_router
from app.routes.policy_insert import router as policy_insert_router
from app.routes.organization import router as organization_router
from app.routes.documents import router as documents_router
from app.routes.search import router as search_router
from app.routes.policy_generate import router as policy_generate_router
from app.routes.policy_embedding import router as policy_embedding_router
from app.routes.policy_alignment import router as policy_alignment_router
from fastapi.middleware.cors import CORSMiddleware
from app.services.weaviate_client import get_weaviate_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Connect to Weaviate
    client = get_weaviate_client()
    if not client.is_connected():
        client.connect()
    yield
    # Shutdown: Cleanup
    if client.is_connected():
        client.close()

app = FastAPI(lifespan=lifespan)

# Allow frontend CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["http://localhost:3000"] for React
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(chatbot_router, prefix="/policy", tags=["Chatbot"])
app.include_router(policy_insert_router, prefix="/policy", tags=["Policy Insert"])
app.include_router(organization_router, prefix="/policy", tags=["Organization"])
app.include_router(documents_router, prefix="/policy", tags=["Documents"])
app.include_router(search_router, prefix="/policy", tags=["Search"])

app.include_router(policy_generate_router, prefix="/policy", tags=["Policy Generate"])
app.include_router(policy_embedding_router, prefix="/policy", tags=["Policy Embedding"])
app.include_router(policy_alignment_router, prefix="/policy", tags=["Policy Alignment"])

@app.get("/")
def read_root():
    return {"message": "Welcome to the Policy Management API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)




# @app.get("/api/policies")
# def get_policies():
#     query = """
#     {
#       Get {
#         Policy {
#           title
#           summary
#           category
#           created_at
#           last_updated
#           source
#         }
#       }
#     }
#     """
#     result = client.query.raw(query)
#     policies = result.get("data", {}).get("Get", {}).get("Policy", [])
#     return policies


# import fitz  # PyMuPDF
# import requests

# @app.get("/api/read-policy")
# def read_policy():

#     url = "https://res.cloudinary.com/dbnf4vmma/raw/upload/v1753779429/policies/provider-registration-policy.pdf"
#     response = requests.get(url)
#     print(f"Response status code: {response.status_code}")
#     if response.status_code != 200:
#         print("Failed to fetch the PDF file.")

#     print("Extracting text from PDF...", response.content[:100])  # Print first 100 bytes for debugging
#     doc = fitz.open(stream=response.content, filetype="pdf")
#     text = ""
#     for page in doc:
#         text += page.get_text()

#     return {"text": text}