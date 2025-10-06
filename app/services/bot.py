import asyncio
import aiohttp
from urllib import response
import openai
from app.services.weaviate_client import get_weaviate_client
from weaviate.classes.query import Filter, MetadataQuery
from fastapi.responses import JSONResponse
from app.config import OPENAI_API_KEY, BACKEND_HISTORY_URL, BACKEND_DOC_READ_COUNT_URL
from openai import AsyncOpenAI
from collections import defaultdict
from app.services.llm_response_correction import extract_json_from_llm
from app.services.store_used_token import used_token_store
import json


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


async def build_context_from_weaviate_results(organization: str, query_text: str, 
                                              category: str = "", document_type: str = "",
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

        # Vector search on latest objects only
        uuids = [str(obj.uuid) for obj in latest_objs]
        uuid_filter = Filter.by_id().contains_any(uuids)

        vector_response = collection.query.near_text(
            query=query_text,
            filters=uuid_filter,
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


async def fetch_history_async(auth_token: str):
    """Async function to fetch chat history"""
    header = {"Authorization": f"Bearer {auth_token}"}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(BACKEND_HISTORY_URL, headers=header) as response:
                if response.status == 200:
                    print("History get successfully--------")
                    data = await response.json()
                    return {
                        "success": True,
                        "remaining_tokens": data['data'].get('remaining_tokens', None),
                        "histories": data['data'].get('histories', [])[:10]
                    }
                else:
                    print(f"History get failed: {response.status}")
                    return {"success": False, "remaining_tokens": None, "histories": []}
        except Exception as e:
            print(f"Error fetching history: {e}")
            return {"success": False, "remaining_tokens": None, "histories": []}


async def save_data_parallel(history_data: dict, readcount_data: dict, 
                            token_data: dict, auth_token: str):
    """Save history, read count, and token data in parallel"""
    header = {"Authorization": f"Bearer {auth_token}"}
    
    async def post_history():
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(BACKEND_HISTORY_URL, json=history_data, 
                                       headers=header) as response:
                    return {"type": "history", "status": response.status}
            except Exception as e:
                print(f"Error saving history: {e}")
                return {"type": "history", "status": 500, "error": str(e)}
    
    async def post_readcount():
        if not readcount_data:
            return {"type": "readcount", "status": 200, "skipped": True}
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(BACKEND_DOC_READ_COUNT_URL, json=readcount_data,
                                       headers=header) as response:
                    return {"type": "readcount", "status": response.status}
            except Exception as e:
                print(f"Error saving read count: {e}")
                return {"type": "readcount", "status": 500, "error": str(e)}
    
    async def post_token():
        # Convert sync function to async - you may need to modify this based on your implementation
        try:
            # If used_token_store is sync, wrap it
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: used_token_store(
                    type='chatbot', 
                    used_tokens=token_data['used_tokens'], 
                    auth_token=auth_token
                )
            )
            return {"type": "token", "status": response.status_code}
        except Exception as e:
            print(f"Error saving token: {e}")
            return {"type": "token", "status": 500, "error": str(e)}
    
    # Execute all three POST requests in parallel
    results = await asyncio.gather(
        post_history(),
        post_readcount(),
        post_token(),
        return_exceptions=True
    )
    
    return results


async def ask_doc_bot(question: str, organization: str, auth_token: str):
    """
    Optimized version with parallel execution:
    - Fetch history and build context in parallel
    - Save all data (history, readcount, token) in parallel
    """
    
    # ============ STEP 1: PARALLEL FETCH (History + Context) ============
    print("⏱️ Starting parallel fetch...")
    start_time = asyncio.get_event_loop().time()
    
    history_task = fetch_history_async(auth_token)
    context_task = build_context_from_weaviate_results(
        organization=organization,
        query_text=question,
        category="",
        document_type=""
    )
    
    # Wait for both to complete
    history_result, context = await asyncio.gather(history_task, context_task)
    
    fetch_time = asyncio.get_event_loop().time() - start_time
    print(f"✅ Parallel fetch completed in {fetch_time:.2f}s")
    
    # Check token limit
    if history_result['remaining_tokens'] is not None and history_result['remaining_tokens'] < 1000:
        return JSONResponse(status_code=400, content={
            "status": "error",
            "message": "Insufficient tokens to continue the conversation."
        })
    
    # Build chat history
    chat_history = []
    for h in history_result['histories']:
        chat_history.append({"role": "user", "content": h['prompt']})
        chat_history.append({"role": "assistant", "content": h['response']})
    
    # ============ STEP 2: LLM CALL ============
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
    
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_history)
    
    if context:
        user_content = f"Context:\n{context}\n\nQuestion: {question}"
    else:
        user_content = f"Question: {question}"
    
    messages.append({"role": "user", "content": user_content})
    
    # GPT-4 call
    print("⏱️ Starting LLM call...")
    llm_start = asyncio.get_event_loop().time()
    
    async with AsyncOpenAI(api_key=OPENAI_API_KEY) as openai_client:
        response = await openai_client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.3
        )
    
    llm_time = asyncio.get_event_loop().time() - llm_start
    print(f"✅ LLM call completed in {llm_time:.2f}s")
    
    used_tokens = response.usage.total_tokens
    answer = response.choices[0].message.content.strip()
    json_answer = extract_json_from_llm(answer)
    
    # Ensure we have a dict
    if isinstance(json_answer, str):
        try:
            json_answer = json.loads(json_answer.replace("'", '"'))
        except Exception:
            json_answer = {
                "answer": json_answer,
                "used_document": False
            }
    
    print('Bot answer after LLM parser------------\n', json_answer)
    
    # ============ STEP 3: PARALLEL SAVE (History + ReadCount + Token) ============
    print("⏱️ Starting parallel save...")
    save_start = asyncio.get_event_loop().time()
    
    # Prepare read count data
    readcount_data = {}
    if json_answer['used_document'] and context:
        for c in context:
            doc_id = c.properties.get("document_id", "")
            readcount_data[doc_id] = 1
        print("Document ID list--\n", readcount_data)
    
    # Prepare data for parallel save
    history_data = {
        "prompt": question,
        "response": json_answer['answer'],
        "used_tokens": used_tokens
    }
    
    token_data = {
        "used_tokens": used_tokens
    }
    
    # Save all in parallel
    save_results = await save_data_parallel(
        history_data, 
        readcount_data, 
        token_data, 
        auth_token
    )
    
    save_time = asyncio.get_event_loop().time() - save_start
    print(f"✅ Parallel save completed in {save_time:.2f}s")
    
    # Check for errors
    for result in save_results:
        if isinstance(result, dict):
            if result['status'] not in [200, 201] and not result.get('skipped'):
                print(f"⚠️ Warning: {result['type']} save failed with status {result['status']}")
                # Don't return error, just log it - user still gets their answer
    
    total_time = asyncio.get_event_loop().time() - start_time
    print(f"🎯 Total request time: {total_time:.2f}s")
    
    # Finally return
    return JSONResponse(status_code=200, content={
        "status": "success",
        "question": question,
        "answer": json_answer['answer'],
        "used_tokens": used_tokens,
        "performance": {
            "fetch_time": f"{fetch_time:.2f}s",
            "llm_time": f"{llm_time:.2f}s",
            "save_time": f"{save_time:.2f}s",
            "total_time": f"{total_time:.2f}s"
        }
    })


# Test function
if __name__ == "__main__":
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzYwODUzMTU5LCJpYXQiOjE3NTgyNjExNTksImp0aSI6ImExM2ExOGI0YWIwNTRmMWI5NDUxMDVlYmZiMTE0NTRmIiwidXNlcl9pZCI6IjcifQ.iHJDqnwOyfJDNQbwF-3kI4fH4bif-37mIElm_ZC4hxA"
    org = "HomeCare"
    q = "Who can apply to be a registered provider under this policy?"
    response = asyncio.run(ask_doc_bot(q, org, token))
    print("\n📊 Final Response:\n", json.loads(response.body))



# START
#  │
#  ├───⏱️ Parallel Fetch ────────────────────────────┐
#  │   ├─ fetch_history_async()                      │
#  │   └─ build_context_from_weaviate_results()      │
#  │                   ↓                             │
#  ├────────────────── Merge Results ────────────────┘
#  │
#  ├─── LLM Call (GPT-4)
#  │
#  ├───⏱️ Parallel Save ─────────────────────────────┐
#  │   ├─ post_history()                             │
#  │   ├─ post_readcount()                           │
#  │   └─ post_token()                               │
#  │                   ↓                             │
#  └────────────────── Merge Results ────────────────┘
#  ↓
# RETURN Final JSONResponse ✅
