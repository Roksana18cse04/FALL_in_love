from fastapi import FastAPI
from app.routes import router
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()


# Allow frontend CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["http://localhost:3000"] for React
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.services.weaviate_client import client

if not client.is_connected():
    client.connect()

app.include_router(router, prefix="/policy", tags=['Operation'])

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