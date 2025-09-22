# FALL_in_love: Policy Management API

A FastAPI-based backend for uploading, embedding, searching, and aligning policy documents using OpenAI and Weaviate.

## Features
- Upload PDF policies, extract and embed content with OpenAI
- Store and search embeddings in Weaviate vector database
- Check alignment of user-uploaded PDFs with stored policies
- Generate policies using LLM with super admin law context
- Dropbox integration for file storage

## Tech Stack
- Python 3.10+
- FastAPI
- Weaviate (Cloud)
- OpenAI API
- Dropbox API
- pdfplumber (PDF extraction)
- Uvicorn (ASGI server)

## Setup

### 1. Clone the repository
```bash
git clone <repo-url>
cd FALL_in_love
```

### 2. Create and activate a virtual environment
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
Create a `.env` file in the root directory with the following keys:
```
OPENAI_API_KEY=your-openai-key
WEAVIATE_API_KEY=your-weaviate-key
WEAVIATE_HOST=your-weaviate-host
DROPBOX_APP_KEY=your-dropbox-app-key
DROPBOX_APP_SECRET=your-dropbox-app-secret
DROPBOX_REFRESH_TOKEN=your-dropbox-refresh-token
```

### 5. Run the server
```bash
uvicorn app.main:app --reload
```

## API Endpoints

### Upload and Embed Policy PDF (Admin)
`POST /policy/admin/upload-policy-pdf`
- Upload a PDF file, extract content, generate embedding, and store in Weaviate.

### Check Policy Alignment (User)
`POST /policy/user/check-policy-alignment`
- Input: PDF file (multipart/form-data, field name `file`).
- Process:
  - Extract full text from PDF
  - Cosine similarity against stored policy embeddings to compute `not_alignment_percent`
  - LLM summarizes the PDF and the main policies (high-context via chunking)
  - LLM returns a single contradiction paragraph; if no direct contradictions, it states that and highlights key differences
- Response example:
```json
{
  "not_alignment_percent": 42.5,
  "contradiction_paragraph": "There are no direct contradictions... main differences are ..."
}
```

### Summarize PDF and Policies (Utility)
`POST /policy/user/summarize-pdf-and-policies`
- Returns brief summaries of the uploaded PDF and the main policies. Useful for debugging/inspection.

### Generate Policy with LLM
`POST /policy/generate-policy`
- Generate a policy using LLM with super admin law context.

### Insert Policy (with Dropbox upload)
`POST /policy/insert-policy`
- Insert a policy document, upload to Dropbox, extract and summarize content, and store in Weaviate.

### Search and List Documents
- `GET /policy/search/hybrid` - Hybrid search (semantic + keyword)
- `GET /policy/documents` - List all documents

## Folder Structure
```
app/
  routes/           # FastAPI route handlers
  services/         # Business logic, integrations (OpenAI, Weaviate, Dropbox)
  data/             # Sample data files
  utils/            # Utility scripts
  config.py         # Loads environment variables
main.py             # FastAPI app entrypoint
requirements.txt    # Python dependencies
.env                # Environment variables (not committed)
```

## Notes
- Ensure your Weaviate instance is reachable.
- For large PDFs/policies, the service chunks text and uses a high max context for LLM summarization.
- Cosine similarity uses OpenAI embeddings; `not_alignment_percent` is `100 - max_similarity*100`.

## License
MIT
