import asyncio
import aiohttp
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
from app.services.cross_encoder_model import LocalReranker


# Initialize global reranker (loaded once at startup)
reranker = LocalReranker()


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




async def rerank_documents_async(query: str, documents: list, top_k: int = 5):
    """
    Async wrapper for reranking to avoid blocking
    Runs reranking in thread pool
    """
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            reranker.rerank,
            query,
            documents,
            top_k
        )
    except Exception as e:
        print(f"❌ Reranking failed: {e}")
        raise Exception(f"Document reranking failed: {str(e)}")


async def build_context_from_weaviate_results(organization: str, query_text: str, 
                                              category: str = "", document_type: str = "",
                                              initial_limit: int = 20, final_limit: int = 5, 
                                              alpha: float = 0.5, include_law: bool = True):
    """
    Step 1: Filter objects by metadata
    Step 2: Pick latest version per title  
    Step 3: Vector search from organization + law collections
    Step 4: Rerank locally using cross-encoder
    """
    client = get_weaviate_client()
    all_documents = []

    try:
        if not client.is_connected():
            client.connect()

        # Fetch from organization collection
        print(f"🔍 Searching in organization: {organization}")
        org_collection = client.collections.get(organization)
        org_results = org_collection.query.fetch_objects()
        org_latest = pick_latest_per_title(org_results.objects)
        print(f"📄 Organization documents found: {len(org_latest)}")
        
        # Always fetch from ALL law collections for ALL organizations
        law_documents = []
        law_collections = ["AgedCareAct", "HomeCareAct", "NDIS", "GeneralAct"]
        
        print(f"🔍 Searching in law collections: {law_collections}")
        for law_collection_name in law_collections:
            try:
                law_collection = client.collections.get(law_collection_name)
                law_results = law_collection.query.fetch_objects()
                collection_docs = pick_latest_per_title(law_results.objects)
                law_documents.extend(collection_docs)
                print(f"⚖️ Found {len(collection_docs)} documents from {law_collection_name}")
                
                # Debug: Show first document if available
                if collection_docs:
                    first_doc = collection_docs[0]
                    print(f"   Sample doc: {first_doc.properties.get('title', 'No title')[:50]}...")
            except Exception as e:
                print(f"⚠️ {law_collection_name} collection not found: {e}")
        
        print(f"⚖️ Total law documents available for {organization}: {len(law_documents)}")
        
        # Combine both collections
        all_latest_objs = org_latest + law_documents
        print(f"📚 Total documents for {organization}: {len(org_latest)} org + {len(law_documents)} law = {len(all_latest_objs)}")

        if not all_latest_objs:
            return []

        # Vector search across combined documents
        uuids = [str(obj.uuid) for obj in all_latest_objs]
        uuid_filter = Filter.by_id().contains_any(uuids)

        # Search in organization collection
        org_vector_response = org_collection.query.near_text(
            query=query_text,
            filters=Filter.by_id().contains_any([str(obj.uuid) for obj in org_latest]),
            limit=initial_limit//2,
            return_metadata=MetadataQuery(score=True)
        )
        
        # Search across ALL law collections equally
        law_vector_objects = []
        if law_documents:
            law_collections = ["AgedCareAct", "HomeCareAct", "NDIS", "GeneralAct"]
            
            for law_collection_name in law_collections:
                try:
                    law_collection = client.collections.get(law_collection_name)
                    
                    response = law_collection.query.near_text(
                        query=query_text,
                        limit=initial_limit//len(law_collections),
                        return_metadata=MetadataQuery(score=True)
                    )
                    if response and response.objects:
                        law_vector_objects.extend(response.objects)
                        print(f"⚖️ Found {len(response.objects)} results from {law_collection_name}")
                except Exception as e:
                    print(f"⚠️ Search failed in {law_collection_name}: {e}")
        
        # Combine results
        combined_objects = []
        if org_vector_response and org_vector_response.objects:
            combined_objects.extend(org_vector_response.objects)
        if law_vector_objects:
            combined_objects.extend(law_vector_objects)
        
        if not combined_objects:
            print("⚠️ No documents found matching the criteria")
            print(f"Debug for {organization}: org_latest={len(org_latest)}, law_documents={len(law_documents)}")
            print(f"Query was: '{query_text}'")
            if law_documents:
                print(f"Available law docs: {[doc.properties.get('title', 'No title')[:30] for doc in law_documents[:3]]}")
            return []
        
        print(f"🔍 Combined search returned {len(combined_objects)} candidates (org: {len(org_vector_response.objects) if org_vector_response and org_vector_response.objects else 0}, law: {len(law_vector_objects)})")
        
        # Separate organization and law results for reranking
        org_objects = org_vector_response.objects if org_vector_response and org_vector_response.objects else []
        
        # Rerank organization documents
        org_context = []
        if org_objects:
            org_reranked = await rerank_documents_async(
                query=query_text,
                documents=org_objects,
                top_k=min(3, len(org_objects))
            )
            org_context = [item['document'] for item in org_reranked]
        
        # Rerank law documents
        law_context = []
        if law_vector_objects:
            law_reranked = await rerank_documents_async(
                query=query_text,
                documents=law_vector_objects,
                top_k=min(3, len(law_vector_objects))
            )
            law_context = [item['document'] for item in law_reranked]
        
        return {
            "org_context": org_context,
            "law_context": law_context
        }

    except Exception as e:
        print(f"❌ Weaviate query failed: {e}")
        raise Exception(f"Failed to retrieve context from database: {str(e)}")
    finally:
        if client.is_connected():
            client.close()


# async def fetch_history_async(auth_token: str):
#     """Async function to fetch chat history"""
#     header = {"Authorization": f"Bearer {auth_token}"}
    
#     async with aiohttp.ClientSession() as session:
#         try:
#             async with session.get(BACKEND_HISTORY_URL, headers=header) as response:
#                 if response.status == 200:
#                     print("History get successfully--------")
#                     data = await response.json()
#                     return {
#                         "success": True,
#                         "remaining_tokens": data['data'].get('remaining_tokens', None),
#                         "histories": data['data'].get('histories', [])[:10]
#                     }
#                 else:
#                     print(f"History get failed: {response.status}")
#                     return {"success": False, "remaining_tokens": None, "histories": []}
#         except Exception as e:
#             print(f"Error fetching history: {e}")
#             return {"success": False, "remaining_tokens": None, "histories": []}


# async def save_data_parallel(history_data: dict, readcount_data: dict, 
#                             token_data: dict, auth_token: str):
#     """Save history, read count, and token data in parallel"""
#     header = {"Authorization": f"Bearer {auth_token}"}
    
#     async def post_history():
#         async with aiohttp.ClientSession() as session:
#             try:
#                 async with session.post(BACKEND_HISTORY_URL, json=history_data, 
#                                        headers=header) as response:
#                     return {"type": "history", "status": response.status}
#             except Exception as e:
#                 print(f"Error saving history: {e}")
#                 return {"type": "history", "status": 500, "error": str(e)}
    
#     async def post_readcount():
#         if not readcount_data:
#             return {"type": "readcount", "status": 200, "skipped": True}
#         async with aiohttp.ClientSession() as session:
#             try:
#                 async with session.post(BACKEND_DOC_READ_COUNT_URL, json=readcount_data,
#                                        headers=header) as response:
#                     return {"type": "readcount", "status": response.status}
#             except Exception as e:
#                 print(f"Error saving read count: {e}")
#                 return {"type": "readcount", "status": 500, "error": str(e)}
    
#     async def post_token():
#         # Convert sync function to async - you may need to modify this based on your implementation
#         try:
#             # If used_token_store is sync, wrap it
#             loop = asyncio.get_event_loop()
#             response = await loop.run_in_executor(
#                 None, 
#                 lambda: used_token_store(
#                     type='chatbot', 
#                     used_tokens=token_data['used_tokens'], 
#                     auth_token=auth_token
#                 )
#             )
#             return {"type": "token", "status": response.status_code}
#         except Exception as e:
#             print(f"Error saving token: {e}")
#             return {"type": "token", "status": 500, "error": str(e)}
    
#     # Execute all three POST requests in parallel
#     results = await asyncio.gather(
#         post_history(),
#         post_readcount(),
#         post_token(),
#         return_exceptions=True
#     )
    
#     return results
async def fetch_history_async(auth_token: str, limit: int = 10, offset: int = 0):
    """Async function to fetch chat history with pagination and dynamic error handling"""
    header = {"Authorization": f"Bearer {auth_token}"}
    params = {"limit": limit, "offset": offset}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(BACKEND_HISTORY_URL, headers=header, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                status = response.status
                
                if status == 200:
                    print("✅ History retrieved successfully")
                    data = await response.json()
                    return {
                        "success": True,
                        "remaining_tokens": data.get('data', {}).get('remaining_tokens', None),
                        "histories": data.get('data', {}).get('histories', [])
                    }
                elif response.status == 401:
                    # Unauthorized
                    return {"success": False, "error": "Unauthorized", "message": "You are unauthorized to access this resource."}
                else:
                    # Dynamic error handling - extract message from server
                    error_message = f"Request failed with status {status}"
                    try:
                        error_data = await response.json()
                        error_message = error_data.get('message', error_data.get('detail', error_message))
                    except:
                        pass
                    
                    print(f"❌ History fetch failed [{status}]: {error_message}")
                    return {
                        "success": False,
                        "error": f"http_{status}",
                        "message": error_message,
                        "status_code": status
                    }
    except Exception as e:
        # All errors (timeout, connection, parse, etc.) handled here
        print(f"❌ History fetch error: {type(e).__name__} - {str(e)}")
        
        # Determine appropriate status code
        status_code = 503
        if isinstance(e, asyncio.TimeoutError):
            status_code = 504
            error_msg = "Request timed out"
        elif isinstance(e, (aiohttp.ClientConnectionError, aiohttp.ClientError)):
            status_code = 503
            error_msg = "Failed to connect to server"
        else:
            status_code = 500
            error_msg = f"Unexpected error: {str(e)}"
        
        return {
            "success": False,
            "error": type(e).__name__.lower(),
            "message": error_msg,
            "status_code": status_code
        }


async def save_data_parallel(history_data: dict, readcount_data: dict, 
                            token_data: dict, auth_token: str):
    """Save history, read count, and token data in parallel with dynamic error handling"""
    header = {"Authorization": f"Bearer {auth_token}"}
    
    async def post_with_error_handling(url: str, data: dict, request_type: str):
        """Generic POST handler with single exception block"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=header, 
                                       timeout=aiohttp.ClientTimeout(total=10)) as response:
                    status = response.status
                    
                    if status in [200, 201]:
                        return {"type": request_type, "status": status, "success": True}
                    else:
                        # Extract error message from response
                        error_msg = f"Failed with status {status}"
                        try:
                            error_data = await response.json()
                            error_msg = error_data.get('message', error_data.get('detail', error_msg))
                        except:
                            pass
                        
                        print(f"❌ {request_type} save failed [{status}]: {error_msg}")
                        return {
                            "type": request_type,
                            "status": status,
                            "success": False,
                            "error": error_msg
                        }
        except Exception as e:
            # All errors handled in one block
            print(f"❌ {request_type} save error: {type(e).__name__} - {str(e)}")
            
            status_code = 503
            if isinstance(e, asyncio.TimeoutError):
                status_code = 504
            
            return {
                "type": request_type,
                "status": status_code,
                "success": False,
                "error": str(e)
            }
    
    async def post_history():
        return await post_with_error_handling(BACKEND_HISTORY_URL, history_data, "history")
    
    async def post_readcount():
        if not readcount_data:
            return {"type": "readcount", "status": 200, "skipped": True, "success": True}
        return await post_with_error_handling(BACKEND_DOC_READ_COUNT_URL, readcount_data, "readcount")
    
    async def post_token():
        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None, 
                lambda: used_token_store(
                    type='chatbot', 
                    used_tokens=token_data['used_tokens'], 
                    auth_token=auth_token
                )
            )
            
            status = resp.status_code if hasattr(resp, 'status_code') else 200
            if status in [200, 201]:
                return {"type": "token", "status": status, "success": True}
            else:
                error_msg = f"Failed with status {status}"
                try:
                    error_msg = resp.json().get('message', error_msg) if hasattr(resp, 'json') else error_msg
                except:
                    pass
                
                print(f"❌ Token save failed [{status}]: {error_msg}")
                return {
                    "type": "token",
                    "status": status,
                    "success": False,
                    "error": error_msg
                }
        except Exception as e:
            print(f"❌ Token save error: {type(e).__name__} - {str(e)}")
            return {
                "type": "token",
                "status": 500,
                "success": False,
                "error": str(e)
            }
    
    results = await asyncio.gather(
        post_history(),
        post_readcount(),
        post_token(),
        return_exceptions=True
    )
    
    return results


# async def ask_doc_bot(question: str, organization: str, auth_token: str):
#     try:
#         # ============ STEP 1: PARALLEL FETCH (History + Context) ============
#         print("⏱️ Starting parallel fetch...")
#         start_time = asyncio.get_event_loop().time()
        
#         history_task = fetch_history_async(auth_token)
#         context_task = build_context_from_weaviate_results(
#             organization=organization,
#             query_text=question,
#             category="",
#             document_type=""
#         )
        
#         # Wait for both to complete
#         history_result, context = await asyncio.gather(history_task, context_task)
        
#         fetch_time = asyncio.get_event_loop().time() - start_time
#         print(f"✅ Parallel fetch completed in {fetch_time:.2f}s")
        
#         # Check token limit
#         if history_result['remaining_tokens'] is not None and history_result['remaining_tokens'] < 1000:
#             return JSONResponse(status_code=400, content={
#                 "status": "error",
#                 "message": "Insufficient tokens to continue the conversation."
#             })
        
#         # Build chat history
#         chat_history = []
#         for h in history_result['histories']:
#             chat_history.append({"role": "user", "content": h['prompt']})
#             chat_history.append({"role": "assistant", "content": h['response']})
        
        # # ============ STEP 2: LLM CALL ============
        # system_prompt = (
        #     "You are Nestor AI, a smart, friendly, and compassionate digital assistant specifically designed to support senior citizens. "
        #     "Your primary mission is to help older adults navigate policies, services, benefits, and general information questions with clarity and empathy.\n\n"
            
        #     "## Identity & Personality\n"
        #     "- When asked 'Who are you?' or similar questions, warmly introduce yourself as Nestor AI, a dedicated helpful assistant for seniors and their families.\n"
        #     "- Maintain a patient, respectful, and encouraging tone in all interactions.\n"
        #     "- Use clear, simple language while avoiding condescension.\n\n"
            
        #     "## Context & Document Handling\n"
        #     "- Each document excerpt includes metadata: Title, Source, Created At, Last Update, document_id, and summary.\n"
        #     "- When answering from provided context documents, ALWAYS cite the source by including the document_id next to the title in this exact format: Title [IR-xxxxxx]\n"
        #     "- If the context documents contain relevant information, prioritize that information in your response.\n"
        #     "- If the answer is not found in the provided context, answer using your general knowledge without limitation.\n"
        #     "- Always be transparent about your information source.\n\n"
            
        #     "## Language Handling\n"
        #     "- If the user writes in English, reply in English.\n"
        #     "- If the user writes in another language, reply in that language.\n"
        #     "- If the user mixes languages naturally (code-switching), mirror that style in your response.\n\n"
            
        #     "## Response Format\n"
        #     "Always return your response strictly in this JSON format without any additional text or markdown:\n"
        #     "{\n"
        #     '  "answer": "your complete answer here, including citations where applicable",\n'
        #     '  "used_document": true_or_false\n'
        #     "}\n\n"
            
        #     "## Response Guidelines\n"
        #     "- Set used_document to true if you referenced any provided context documents.\n"
        #     "- Set used_document to false if you answered entirely from general knowledge.\n"
        #     "- Provide complete, helpful answers that directly address the user's question.\n"
        #     "- When appropriate, offer additional relevant information that might be helpful.\n"
        # )
        
#         messages = [{"role": "system", "content": system_prompt}]
#         messages.extend(chat_history)
        
#         if context:
#             user_content = f"Context:\n{context}\n\nQuestion: {question}"
#         else:
#             user_content = f"Question: {question}"
        
#         messages.append({"role": "user", "content": user_content})
        
#         # GPT-4 call
#         print("⏱️ Starting LLM call...")
#         llm_start = asyncio.get_event_loop().time()
        
#         async with AsyncOpenAI(api_key=OPENAI_API_KEY) as openai_client:
#             response = await openai_client.chat.completions.create(
#                 model="gpt-4",
#                 messages=messages,
#                 temperature=0.3
#             )
        
#         llm_time = asyncio.get_event_loop().time() - llm_start
#         print(f"✅ LLM call completed in {llm_time:.2f}s")
        
#         used_tokens = response.usage.total_tokens
#         answer = response.choices[0].message.content.strip()
#         json_answer = extract_json_from_llm(answer)
        
#         # Ensure we have a dict
#         if isinstance(json_answer, str):
#             try:
#                 json_answer = json.loads(json_answer.replace("'", '"'))
#             except Exception:
#                 json_answer = {
#                     "answer": json_answer,
#                     "used_document": False
#                 }
        
#         print('Bot answer after LLM parser------------\n', json_answer)
        
#         # ============ STEP 3: PARALLEL SAVE (History + ReadCount + Token) ============
#         print("⏱️ Starting parallel save...")
#         save_start = asyncio.get_event_loop().time()
        
#         # Prepare read count data
#         readcount_data = {}
#         if json_answer['used_document'] and context:
#             for c in context:
#                 doc_id = c.properties.get("document_id", "")
#                 readcount_data[doc_id] = 1
#             print("Document ID list--\n", readcount_data)
        
#         # Prepare data for parallel save
#         history_data = {
#             "prompt": question,
#             "response": json_answer['answer'],
#             "used_tokens": used_tokens
#         }
        
#         token_data = {
#             "used_tokens": used_tokens
#         }
        
#         # Save all in parallel
#         save_results = await save_data_parallel(
#             history_data, 
#             readcount_data, 
#             token_data, 
#             auth_token
#         )
        
#         save_time = asyncio.get_event_loop().time() - save_start
#         print(f"✅ Parallel save completed in {save_time:.2f}s")
        
#         # Check for errors
#         for result in save_results:
#             if isinstance(result, dict):
#                 if result['status'] not in [200, 201] and not result.get('skipped'):
#                     print(f"⚠️ Warning: {result['type']} save failed with status {result['status']}")
#                     # Don't return error, just log it - user still gets their answer
        
#         total_time = asyncio.get_event_loop().time() - start_time
#         print(f"🎯 Total request time: {total_time:.2f}s")
        
#         # Finally return
#         return JSONResponse(status_code=200, content={
#             "status": "success",
#             "question": question,
#             "answer": json_answer['answer'],
#             "used_tokens": used_tokens,
#             "performance": {
#                 "fetch_time": f"{fetch_time:.2f}s",
#                 "llm_time": f"{llm_time:.2f}s",
#                 "save_time": f"{save_time:.2f}s",
#                 "total_time": f"{total_time:.2f}s"
#             }
#         })
    
#     except Exception as e:
#         print(f"❌ ask_doc_bot failed:--------- {str(e)}")
#         raise e
async def ask_doc_bot(question: str, organization: str, auth_token: str):
    try:
        # ================= STEP 0: Check Auth Token =================
        history_result = await fetch_history_async(auth_token)
        if not history_result.get("success", True):
            if history_result.get("error") == "Unauthorized":
                return JSONResponse(
                    status_code=401,
                    content={
                        "success": False,
                        "error": "Unauthorized",
                        "message": "You are unauthorized to access this resource."
                    }
                )

        # ================= STEP 1: PARALLEL FETCH (History + Context) =================
        print("⏱️ Starting parallel fetch...")
        start_time = asyncio.get_event_loop().time()
        
        try:
            history_task = fetch_history_async(auth_token)
            context_task = build_context_from_weaviate_results(
                organization=organization,
                query_text=question,
                initial_limit=20,
                final_limit=5,
                include_law=True  # Always include all law collections
            )
            
            history_result, context_result = await asyncio.gather(history_task, context_task)
            
            # Extract separate contexts
            org_context = context_result.get("org_context", []) if isinstance(context_result, dict) else []
            law_context = context_result.get("law_context", []) if isinstance(context_result, dict) else []
            
        except Exception as e:
            print(f"❌ Parallel fetch failed: {e}")
            return JSONResponse(status_code=500, content={
                "status": "error",
                "message": "Failed to retrieve necessary data",
                "error": str(e)
            })
        
        fetch_time = asyncio.get_event_loop().time() - start_time
        print(f"✅ Parallel fetch completed in {fetch_time:.2f}s")
        
        # ============ CHECK HISTORY FETCH ERRORS ============
        if not history_result['success']:
            error_code = history_result.get('status_code', 500)
            error_message = history_result.get('message', 'Failed to fetch chat history')
            
            print(f"❌ History fetch failed: {error_message}")
            return JSONResponse(status_code=error_code, content={
                "status": "error",
                "message": error_message,
                "error_type": history_result.get('error', 'unknown_error')
            })
        
        # ============ CHECK TOKEN LIMIT ============
        if history_result['remaining_tokens'] is not None and history_result['remaining_tokens'] < 1000:
            print("❌ Insufficient tokens")
            return JSONResponse(status_code=400, content={
                "status": "error",
                "message": "Insufficient tokens to continue the conversation.",
                "remaining_tokens": history_result['remaining_tokens']
            })
        
        # Build chat history
        chat_history = []
        for h in history_result.get('histories', []):
            chat_history.append({"role": "user", "content": h['prompt']})
            chat_history.append({"role": "assistant", "content": h['response']})
        
        # ================= DEBUG CONTEXT =================
        print(f"📄 Org Context: {len(org_context)} docs, Law Context: {len(law_context)} docs")
        if org_context:
            for i, doc in enumerate(org_context[:2]):
                title = doc.properties.get('title', 'No title')[:30]
                print(f"   Org {i+1}: {title}")
        if law_context:
            for i, doc in enumerate(law_context[:2]):
                title = doc.properties.get('title', 'No title')[:30]
                print(f"   Law {i+1}: {title}")
        
        # ================= STEP 2: LLM CALL ================="
               
        system_prompt = (
            "You are Nestor AI, a friendly and knowledgeable assistant specializing in aged care and Australian law. "
            "You communicate with warmth, empathy, and genuine care for helping people understand complex topics.\n\n"
            
            "🎯 **PERSONALITY & STYLE:**\n"
            "- Be conversational, warm, and approachable like a real chatbot\n"
            "- Start with natural responses like 'Sure!', 'Of course!', 'Absolutely!', 'Good question!'\n"
            "- End with encouraging closings like 'Hope this helps!', 'Let me know if you need more info!', 'Happy to help!'\n"
            "- Use natural emojis occasionally to add warmth (🏛️, 📋, ⚖️, 👥, 💡, 🤔)\n"
            "- Break down complex information into digestible, conversational chunks\n"
            "- Use phrases like 'Here's what I found', 'Based on my knowledge', 'Let me explain this for you'\n"
            "- Show genuine interest with phrases like 'That's a great question!', 'I understand your concern about...'\n\n"
            
            "💬 **CONVERSATIONAL FLOW:**\n"
            "1. **Opening:** Start with a warm greeting that acknowledges the question\n"
            "2. **Body:** Provide the main information in clear, organized but natural sections\n"
            "3. **Closing:** End with an encouraging note and invitation for follow-up\n"
            "4. **Tone:** Maintain helpful, patient, and supportive tone throughout\n\n"
            
            "📝 **ANSWER STRUCTURE EXAMPLES:**\n"
            "For law questions:\n"
            "💡 'Sure! That's an important question about Australian law. Let me break this down for you...'\n"
            "📋 'Based on the Aged Care Act, here are the key points you should know...'\n"
            "🤝 'Hope this clarifies things for you! Feel free to ask if you need more details.'\n\n"
            
            "For policy questions:\n"
            "👋 'Of course! I found some relevant information in your organization's policies...'\n"
            "📄 'According to your organization's documents, here's what applies to your situation...'\n"
            "💫 'Let me know if this answers your question completely!'\n\n"
            
            "🔍 **CONTEXT USAGE RULES:**\n"
            "- LAW QUESTIONS: Use Australian Law Context, set used_document=false\n"
            "- POLICY QUESTIONS: Use organization context, set used_document=true\n"
            "- NEVER mix organization context with law questions\n"
            "- Be transparent: 'Based on Australian legislation...' or 'According to your organization's policy...'\n\n"
            
            "🌍 **MULTILINGUAL SUPPORT:**\n"
            "- ALWAYS respond in the SAME language the user asks in\n"
            "- Support major Australian community languages:\n"
            "  • English: 'Sure!' / 'Of course!'\n"
            "  • Mandarin Chinese: '当然!' / '好的!'\n"
            "  • Arabic: 'بالطبع!' / 'أكيد!'\n"
            "  • Vietnamese: 'Chắc chắn!' / 'Tất nhiên!'\n"
            "  • Italian: 'Certo!' / 'Naturalmente!'\n"
            "  • Greek: 'Φυσικά!' / 'Βέβαια!'\n"
            "  • Hindi: 'ज़रूर!' / 'बिल्कुल!'\n"
            "  • Bengali: 'অবশ্যই!' / 'ঠিক আছে!'\n"
            "- Maintain the same warm, conversational tone in any language\n"
            "- Use culturally appropriate expressions and greetings\n\n"
            
            "📋 **RESPONSE FORMAT (STRICT JSON):**\n"
            "You MUST return ONLY this JSON format - no other text, no markdown, no code blocks:\n"
            "{\n"
            '  "answer": "Your natural, conversational response here with proper opening and closing",\n'
            '  "used_document": true_or_false\n'
            "}\n\n"
            
            "🚫 **FORBIDDEN:**\n"
            "- No markdown formatting (**, ##, etc.)\n"
            "- No code blocks or triple backticks\n"
            "- No nested JSON in answer field\n"
            "- No technical formatting - just natural conversation\n"
            "- No 'As an AI assistant' disclaimers\n\n"
            
            "✅ **GOOD RESPONSE EXAMPLE:**\n"
            "{\n"
            '  "answer": "Sure! That\'s a great question about aged care regulations. Let me explain how this works in Australia...\\n\\nBased on the Aged Care Act 1997, there are several key requirements for providers. The main aspects include quality standards, resident rights, and compliance measures.\\n\\nFor example, Standard 2 focuses on personal and clinical care, while Standard 3 covers services and supports for daily living.\\n\\nHope this gives you a clear understanding! Feel free to ask if you need specifics about any particular standard.",\n'
            '  "used_document": false\n'
            "}\n"
        )
        
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(chat_history)
        formatted_content = ""
        
        # Add organization context if available
        if org_context:
            formatted_content += "ORGANIZATION CONTEXT:\n"
            for i, doc in enumerate(org_context, 1):
                title = doc.properties.get('title', 'Unknown Title')
                version_number = doc.properties.get('version_number', 1)
                document_id = doc.properties.get('document_id', 'Unknown ID')
                data = doc.properties.get('data', '')
                
                formatted_content += f"[Org-{i}] {title} v{version_number} [{document_id}]\n"
                formatted_content += f"{data}\n\n"
        
        # Add law context if available
        if law_context:
            formatted_content += "AUSTRALIAN LAW CONTEXT:\n"
            for i, doc in enumerate(law_context, 1):
                title = doc.properties.get('title', 'Unknown Title')
                version_number = doc.properties.get('version_number', 1)
                document_id = doc.properties.get('document_id', 'Unknown ID')
                data = doc.properties.get('data', '')
                
                formatted_content += f"[Law-{i}] {title} v{version_number} [{document_id}]\n"
                formatted_content += f"{data}\n\n"
        
        # Determine context status for clear instruction
        context_status = ""
        if org_context and law_context:
            context_status = "Both organization and law context available."
        elif org_context:
            context_status = "Only organization context available."
        elif law_context:
            context_status = "Only Australian law context available."
        else:
            context_status = "No specific context available - use general knowledge with disclaimer."
        
        # Determine if this is a law question
        law_keywords = ['law', 'act', 'legislation', 'legal', 'aged care act', 'ndis act', 'regulation']
        is_law_question = any(keyword in question.lower() for keyword in law_keywords)
        
        question_type = "LAW QUESTION" if is_law_question else "POLICY QUESTION"
        
        user_content = f"{formatted_content}QUESTION: {question}\n\nQUESTION TYPE: {question_type}\n\nCONTEXT STATUS: {context_status}\n\nCRITICAL INSTRUCTIONS:\n- This is a {question_type}\n- If LAW QUESTION: Use ONLY Australian Law Context, IGNORE organization context, set used_document=false\n- If POLICY QUESTION: Use organization context, set used_document=true\n- NEVER mix organization context with law questions"
        messages.append({"role": "user", "content": user_content})
        
        print("⏱️ Starting LLM call...")
        llm_start = asyncio.get_event_loop().time()
        
        try:
            async with AsyncOpenAI(api_key=OPENAI_API_KEY) as openai_client:
                response = await openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=messages,
                    temperature=0.3
                )
        except openai.APIError as e:
            print(f"❌ OpenAI API error: {e}")
            return JSONResponse(status_code=503, content={
                "status": "error",
                "message": "AI service temporarily unavailable",
                "error": str(e)
            })
        except openai.RateLimitError as e:
            print(f"❌ OpenAI rate limit exceeded: {e}")
            return JSONResponse(status_code=429, content={
                "status": "error",
                "message": "Too many requests. Please try again later.",
                "error": str(e)
            })
        except Exception as e:
            print(f"❌ LLM call failed: {e}")
            return JSONResponse(status_code=500, content={
                "status": "error",
                "message": "Failed to generate response",
                "error": str(e)
            })
        
        llm_time = asyncio.get_event_loop().time() - llm_start
        print(f"✅ LLM call completed in {llm_time:.2f}s")
        
        used_tokens = response.usage.total_tokens
        answer = response.choices[0].message.content.strip()
        print("🤖 Raw LLM answer:", answer)
        
        try:
            # Decode HTML entities and try direct JSON parsing
            import html
            decoded_answer = html.unescape(answer)
            json_answer = json.loads(decoded_answer)
        except json.JSONDecodeError:
            try:
                # Try extracting JSON from LLM response
                json_answer = extract_json_from_llm(answer)
                if isinstance(json_answer, str):
                    json_answer = json.loads(html.unescape(json_answer))
            except Exception as e:
                print(f"⚠️ JSON parsing failed, using fallback: {e}")
                # Determine used_document based on question type
                law_keywords = ['law', 'act', 'legislation', 'legal', 'aged care act', 'ndis act', 'regulation']
                is_law_question = any(keyword in question.lower() for keyword in law_keywords)
                json_answer = {
                    "answer": answer,
                    "used_document": not is_law_question and bool(org_context)
                }
        
        print('✅ Bot answer after LLM parser:', json_answer)
        
        # ============ STEP 3: PARALLEL SAVE (Non-blocking) ============
        print("⏱️ Starting parallel save...")
        save_start = asyncio.get_event_loop().time()
        
        readcount_data = {}
        if json_answer.get('used_document', False) and org_context:
            for c in org_context:
                doc_id = c.properties.get("document_id", "")
                if doc_id:
                    readcount_data[doc_id] = 1
            print("📄 Organization document IDs to update:", readcount_data)
        
        # Debug: Check if used_document is incorrectly set for law questions
        law_keywords = ['law', 'act', 'legislation', 'legal', 'aged care act', 'ndis act', 'regulation']
        is_law_question = any(keyword in question.lower() for keyword in law_keywords)
        if is_law_question and json_answer.get('used_document', False):
            print("⚠️ WARNING: Law question incorrectly set used_document=true")
        
        history_data = {
            "prompt": question,
            "response": json_answer['answer'],
            "used_tokens": used_tokens
        }
        
        token_data = {"used_tokens": used_tokens}
        
        # Save in background (don't block response)
        try:
            save_results = await save_data_parallel(
                history_data, readcount_data, token_data, auth_token
            )
            
            save_time = asyncio.get_event_loop().time() - save_start
            print(f"✅ Parallel save completed in {save_time:.2f}s")
            
            # Log warnings but don't fail the request
            for result in save_results:
                if isinstance(result, dict) and not result.get('success', False) and not result.get('skipped', False):
                    print(f"⚠️ Warning: {result['type']} save failed with status {result.get('status', 'unknown')}")
        
        except Exception as e:
            # Log but don't fail the request
            print(f"⚠️ Background save failed: {e}")
            save_time = asyncio.get_event_loop().time() - save_start
        
        total_time = asyncio.get_event_loop().time() - start_time
        print(f"🎯 Total request time: {total_time:.2f}s")
        
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
    
    except Exception as e:
        print(f"❌ Unexpected error in ask_doc_bot: {str(e)}")
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": "An unexpected error occurred",
            "error": str(e)
        })
