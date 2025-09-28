from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.routes.chatbot import router as chatbot_router
from app.routes.policy_insert import router as policy_insert_router
from app.routes.create_organization import router as create_organization_router
from app.routes.policy_generate import router as policy_generate_router
from app.routes.policy_embedding import router as policy_embedding_router
from app.routes.policy_alignment import router as policy_alignment_router
from app.routes.delete_document import router as delete_document_router
from app.routes.delete_schema import router as delete_schema_router
from app.routes.summerizer import router as summarizer_router

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
    allow_origins=["http://localhost:5173"],  # or ["http://localhost:3000"] for React
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(chatbot_router,prefix="/document", tags=["Chatbot"])
app.include_router(policy_insert_router, prefix="/document", tags=["Document"])
app.include_router(delete_document_router, prefix="/document", tags=["Document"])
app.include_router(summarizer_router, prefix="/document", tags=["Document"])

app.include_router(create_organization_router, prefix="/organization", tags=["Organization"])
app.include_router(delete_schema_router, prefix="/organization", tags=["Organization"])

app.include_router(policy_generate_router, prefix="/policy", tags=["Policy Generate"])
app.include_router(policy_embedding_router, prefix="/policy", tags=["Policy Embedding"])
app.include_router(policy_alignment_router, prefix="/policy", tags=["Policy Alignment"])

@app.get("/")
def read_root():
    return {"message": "Welcome to the Policy Management API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

