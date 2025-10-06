from urllib import response
import openai
from app.services.weaviate_client import get_weaviate_client
from weaviate.classes.query import Filter, MetadataQuery
from weaviate.classes.query import MetadataQuery
from fastapi.responses import JSONResponse
from app.config import OPENAI_API_KEY, BACKEND_HISTORY_URL, BACKEND_DOC_READ_COUNT_URL
from openai import AsyncOpenAI
import requests
from collections import defaultdict
from app.services.llm_response_correction import extract_json_from_llm
from app.services.store_used_token import used_token_store
    

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

async def build_context_from_weaviate_results(organization: str, query_text: str, category: str, document_type: str,
                    limit: int = 5, alpha: float = 0.5):
    """
    Step 1: Filter objects by metadata (category + document_type)
    Step 2: Pick latest version per title
    Step 3: Do near_text (vector search) only on those UUIDs
    """
    client = get_weaviate_client()

    if not client.is_connected():
        client.connect()

    collection = client.collections.get(organization)

    try:

        results = collection.query.fetch_objects()
        latest_objs = pick_latest_per_title(results.objects)


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
        if not vector_response:
            print("No documents found matching the criteria")
            return []
        return vector_response.objects

    except Exception as e:
        print(f"Query error: {e}")
        return []
    
    finally:
        if client.is_connected():
            client.close()

async def ask_doc_bot(question: str, organization: str, auth_token: str):
    header = {"Authorization": f"Bearer {auth_token}"}
    history_res = requests.get(BACKEND_HISTORY_URL, headers=header)
    
    chat_history = []
    if history_res.status_code == 200:
        print("history get successfully--------")

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
    else: print("history get failed-----------")

    context = ""

    context = await build_context_from_weaviate_results(
        organization=organization,
        query_text=question,
        category="",
        document_type=""
    )
    # print("context-------\n", context)

    # system prompt
    system_prompt = (
        "You are Nestor AI, a smart, friendly, and compassionate digital assistant specifically designed to support senior citizens. "
        "Your primary mission is to help older adults navigate policies, services, benefits, and general information questions with clarity and empathy.\n\n"
        
        "## Identity & Personality\n"
        "- When asked 'Who are you?' or similar questions, warmly introduce yourself as Nestor AI, a dedicated helpful assistant for seniors and their families.\n"
        "- Maintain a patient, respectful, and encouraging tone in all interactions.\n"
        "- Use clear, simple language while avoiding condescension.\n\n"
        
        "## Context & Document Handling\n"
        "- Each document excerpt includes metadata: Title, Source, Created At, Last Update, document_id, and summary.\n"
        "- When answering from provided context documents, ALWAYS cite the source by including the document_id next to the title in this exact format: Title [IR-xxxxxx]\n"
        "- If the context documents contain relevant information, prioritize that information in your response.\n"
        "- If the answer is not found in the provided context, answer using your general knowledge without limitation.\n"
        "- Always be transparent about your information source.\n\n"
        
        "## Language Handling\n"
        "- If the user writes in English, reply in English.\n"
        "- If the user writes in another language, reply in that language.\n"
        "- If the user mixes languages naturally (code-switching), mirror that style in your response.\n\n"
        
        "## Response Format\n"
        "Always return your response strictly in this JSON format without any additional text or markdown:\n"
        "{\n"
        '  "answer": "your complete answer here, including citations where applicable",\n'
        '  "used_document": true_or_false\n'
        "}\n\n"
        
        "## Response Guidelines\n"
        "- Set used_document to true if you referenced any provided context documents.\n"
        "- Set used_document to false if you answered entirely from general knowledge.\n"
        "- Provide complete, helpful answers that directly address the user's question.\n"
        "- When appropriate, offer additional relevant information that might be helpful.\n"
    )

    # build messages
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_history)

    if context:
        user_content = f"Context:\n{context}\n\nQuestion: {question}"
    else:
        user_content = f"Question: {question}"

    messages.append({"role": "user", "content": user_content})

    # GPT-4 call
    async with AsyncOpenAI(api_key=OPENAI_API_KEY) as openai_client:
        response = await openai_client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.3
        )
    used_tokens = response.usage.total_tokens

    answer = response.choices[0].message.content.strip()
    json_answer = extract_json_from_llm(answer)

    # Ensure we have a dict
    if isinstance(json_answer, str):
        try:
            # Try parsing as JSON
            json_answer = json.loads(json_answer.replace("'", '"'))  # Replace single quotes
        except Exception:
            # If it still fails, wrap plain text into dict
            json_answer = {
                "answer": json_answer,
                "used_document": False
            }
    print('bot answr after llm parser------------\n', json_answer)

    # to read count , find out document_title of llm find answer from context
    if json_answer['used_document']:
        document_id_list = {}
        for c in context:
            id = c.properties.get("document_id", "")
            document_id_list[id] = 1
        print("document id list--\n", document_id_list)
        # save document read count
        readCount_payload = document_id_list
        readCount_response = requests.post(BACKEND_DOC_READ_COUNT_URL, json=readCount_payload, headers=header)
        print("readcount response -------------", readCount_response)
        if readCount_response.status_code != 201:
            return JSONResponse(status_code=500, content={
                "status": "error",
                "message": "Failed to save read count data"
                
            })
        else: print("save read count data successfully!")

    # save history
    history_payload = {
        "prompt": question, 
        "response": json_answer['answer'], 
        "used_tokens": used_tokens
    }
    res = requests.post(BACKEND_HISTORY_URL, json=history_payload, headers=header)
    if res.status_code != 201:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": "Failed to save chat history.",
            
        })
    else: print("save history data successfully!")
    
    # save token count
    token_response = used_token_store(type= 'chatbot', used_tokens=used_tokens, auth_token=auth_token)
    if token_response.status_code != 201:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": "Failed to save chatbot used token.",
            
        })
    
    # finally return 
    return JSONResponse(status_code=200, content={
        "status": "success",
        "question": question,
        "answer": json_answer['answer'],
        "used_tokens": used_tokens
    })



import asyncio
import json
if __name__ == "__main__":
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzYwODUzMTU5LCJpYXQiOjE3NTgyNjExNTksImp0aSI6ImExM2ExOGI0YWIwNTRmMWI5NDUxMDVlYmZiMTE0NTRmIiwidXNlcl9pZCI6IjcifQ.iHJDqnwOyfJDNQbwF-3kI4fH4bif-37mIElm_ZC4hxA" 
    org = "HomeCare"
    q = "Who can apply to be a registered provider under this policy?"
    response = asyncio.run(ask_doc_bot(q, org, token))
    print("print from bot main function: \n", json.loads(response.body))
