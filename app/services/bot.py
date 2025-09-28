from urllib import response
import openai
from app.services.weaviate_client import get_weaviate_client
from weaviate.classes.query import Filter, MetadataQuery
from app.services.classification import predict_relevant_category_and_type
from weaviate.classes.query import MetadataQuery
from fastapi.responses import JSONResponse
from app.config import OPENAI_API_KEY
from openai import AsyncOpenAI, OpenAI
import requests
from collections import defaultdict

BACKEND_URL = "https://jahidtestmysite.pythonanywhere.com/ai_chatbot/ChatHistory/"

def _version_number(v):
    """Convert version string like 'v2' or '2' to int for sorting."""
    try:
        if isinstance(v, str) and v.startswith("v"):
            return int(v[1:])
        return int(v)
    except (ValueError, TypeError):
        return 1
    
def pick_latest_per_title(objects):
    grouped = defaultdict(list)
    for obj in objects:
        title = obj.properties.get("title", "")
        grouped[title].append(obj)

    latest = []
    for title, objs in grouped.items():
        best = max(objs, key=lambda o: _version_number(o.properties.get("version")))
        latest.append(best)
    return latest

def build_context_from_weaviate_results(organization: str, query_text: str, category: str, document_type: str,
                    limit: int = 5, alpha: float = 0.5):
    """
    Step 1: Filter objects by metadata (category + document_type)
    Step 2: Pick latest version per title
    Step 3: Do near_text (vector search) only on those UUIDs
    """
    client = get_weaviate_client()

    if not client.is_connected():
        client.connect()

    collection = client.collections.get("HomeCare")

    try:
        # --- Step 1: Metadata filter ---
        filtered = collection.query.fetch_objects(
            filters=(
                Filter.by_property("category").equal(category) &
                Filter.by_property("document_type").equal(document_type)
            ),
            limit=9999  # Pull all matching to handle versioning
        )

        if not filtered.objects:
            print("No documents found matching the criteria")
            return []

        print(f"Filtered to {len(filtered.objects)} documents")

        # --- Step 2: Pick latest version per title ---
        latest_objs = pick_latest_per_title(filtered.objects)
        print(f"Selected {len(latest_objs)} latest version documents")

        # --- Step 3: Vector search on latest objects only ---
        uuids = [str(obj.uuid) for obj in latest_objs]
        uuid_filter = Filter.by_id().contains_any(uuids)

        vector_response = collection.query.near_text(
            query=query_text,
            filters=uuid_filter,
            # alpha=alpha,
            limit=limit,
            return_metadata=MetadataQuery(score=True)
        )
        return vector_response.objects

    except Exception as e:
        print(f"Query error: {e}")
        return []
    
    finally:
        if client.is_connected():
            client.close()

async def ask_doc_bot(question: str, organization: str, auth_token: str):
    header = {"Authorization": f"Bearer {auth_token}"}
    history_res = requests.get(BACKEND_URL, headers=header)

    chat_history = []
    if history_res.status_code == 200:
        data = history_res.json()['data']
        remaining_tokens = data.get('remaining_tokens', None)
        histories = data.get('histories', [])[:10]

        if remaining_tokens is not None and remaining_tokens < 1000:
            return JSONResponse(status_code=400, content={
                "status": "error",
                "message": "Insufficient tokens to continue the conversation."
            })

        for h in histories:
            chat_history.append({"role": "user", "content": h['prompt']})
            chat_history.append({"role": "assistant", "content": h['response']})

    # 🟢 classify question
    classify_response = predict_relevant_category_and_type(question)
    category = classify_response.get("category")
    document_type = classify_response.get("document_type")
    is_doc_related = classify_response.get("is_document_related", False)
    classify_used_tokens = classify_response.get("used_tokens")

    # 🟢 context fetch only if doc-related
    context = ""
    if is_doc_related and category and document_type:
        context = build_context_from_weaviate_results(
            organization=organization,
            query_text=question,
            category=category,
            document_type=document_type
        )
    else:
        context = ""  # no context when not document related

    # 🟢 system prompt
    system_prompt = (
        "You are a helpful assistant. "
        "If context is provided, answer based on it. "
        "If no relevant context is provided, answer from your general knowledge.\n"
        "Each document excerpt includes metadata: Title, Source, Created At, Last Update, document_id.\n"
        "When referencing a document, always include the document_id next to the title in this format: "
        "Title [IR-xxxxxx]. "
        "If the answer is not found in the context, say 'I'm sorry, but without a specific document or context, I can't provide a specific privacy policy. However, in general terms,' and then continue with your own knowledge.\n"
    )

    # 🟢 build messages
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_history)

    # এখানে context থাকলে সেটাও যোগ করো
    if context:
        user_content = f"Context:\n{context}\n\nQuestion: {question}"
    else:
        user_content = f"Question: {question}"

    messages.append({"role": "user", "content": user_content})

    # 🟢 GPT-4 call
    async with AsyncOpenAI(api_key=OPENAI_API_KEY) as openai_client:
        response = await openai_client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.3
        )

    answer = response.choices[0].message.content.strip()
    print("Question:", question)
    print("Answer:", answer)
    used_tokens = response.usage.total_tokens + classify_used_tokens

    # 🟢 save history
    history_payload = {"prompt": question, "response": answer, "used_tokens": used_tokens}
    res = requests.post(BACKEND_URL, json=history_payload, headers=header)

    if res.status_code != 201:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": "Failed to save chat history."
        })

    return JSONResponse(status_code=200, content={
        "status": "success",
        "question": question,
        "answer": answer,
        "used_tokens": used_tokens
    })



import asyncio
import json
if __name__ == "__main__":
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzYwMDczNzk5LCJpYXQiOjE3NTc0ODE3OTksImp0aSI6ImM4NjAzNjU1NmNkZjQwZjdiYzFhYzc5MWE3NWU3MjAwIiwidXNlcl9pZCI6IjcifQ.Q0_AwIaCzvTfTi17XngEbmBBlJOx-An3HkQRetnM3Xg" 
    org = "HomeCare"
    q = "What is the privacy policy? in short"
    response = asyncio.run(ask_doc_bot(q, org, token))
    print(json.loads(response.body))
