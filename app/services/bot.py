import openai
from app.services.weaviate_client import client
from weaviate.classes.query import MetadataQuery
from fastapi.responses import JSONResponse
from app.config import OPENAI_API_KEY
from openai import OpenAI
import requests

openai_client = OpenAI(api_key=OPENAI_API_KEY)

def build_context_from_weaviate_results(query_text, organization, limit=3, alpha=0.5):
    if not client.is_connected():
        client.connect()

    collection = client.collections.get(organization)

    response = collection.query.hybrid(
        query=query_text,
        alpha=alpha,
        limit=limit,
        return_metadata=MetadataQuery(score=True)
        # return_metadata=MetadataQuery(
        #     score=True,
        #     uuid=True,
        #     properties=True  # fetch all properties
        # )
    )

    context_chunks = []
    for obj in response.objects:
        props = obj.properties
        uuid = obj.uuid
        # score = obj.score

        # Format all properties as key: value pairs for context
        excluded_props = {"summary"}
        props_text = "\n".join(
            f"{key}: {value}" 
            for key, value in props.items() if key not in excluded_props
        )
        # print("properties-----------", props)

        chunk = (
            f"UUID: {uuid}\n"
            # f"Score: {score}\n"
            f"Properties:\n{props_text}\n"
            "-----"
        )
        context_chunks.append(chunk)
        # print("context chunk"+"-"*20)
        # print(context_chunks)

    context = "\n\n".join(context_chunks)
    return context.strip()

async def ask_doc_bot(question: str, organization: str, auth_token: str):
    """Ask question to GPT-4 using Weaviate context and short-term memory"""

    # Fetch chat history from DB
    header = {"Authorization": f"Bearer {auth_token}"}
    history_res = requests.get(
        "https://jahidtestmysite.pythonanywhere.com/ai_chatbot/ChatHistory/",
        headers=header
    )

    if history_res.status_code == 200:
        data = history_res.json()['data']
        remaining_tokens = data.get('remaining_tokens', None)
        histories = data.get('histories', [])[:10]

        # Check token limit
        if remaining_tokens is not None and remaining_tokens < 1000:
            return JSONResponse(status_code=400, content={
                "status": "error",
                "message": "Insufficient tokens to continue the conversation."
            })

        # Convert to OpenAI chat format
        chat_history = []
        for h in histories:
            chat_history.append({"role": "user", "content": h['prompt']})
            chat_history.append({"role": "assistant", "content": h['response']})
    else:
        chat_history = []

    print("Chat history from DB:", chat_history)

    try:
        # Build context from Weaviate
        context = build_context_from_weaviate_results(question, organization=organization)

        system_prompt = (
            "You are a helpful assistant that answers questions based on organizational policy documents.\n"
            "Each document excerpt includes metadata: Title, Source, Created At, Last Update, UUID, and Content.\n"
            "When referencing a policy, always include the ID next to the title in this format: Title [IR-xxxxxx], "
            "where 'xxxxxx' is derived from the first 6 characters of the UUID.\n"
            "Use the metadata to answer questions about policy details, such as when it was last updated or where it is sourced from.\n"
            "If the answer is not found in the context, say 'I don't know based on the documents.'"
        )

        # Build messages for GPT-4
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(chat_history)  # Append past conversation
        messages.append({
            "role": "user",
            "content": f"Context:\n{context}\n\nQuestion: {question}"
        })

        # GPT-4 response
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.3
        )

        answer = response.choices[0].message.content.strip()
        # print("Answer from GPT-4:", answer)

        used_tokens = response.usage.total_tokens

        # history add in DB
        history_payload = {
            "prompt": question,
            "response": answer,
            "used_tokens": used_tokens
        }
        res = requests.post(
            "https://jahidtestmysite.pythonanywhere.com/ai_chatbot/ChatHistory/",
            json=history_payload,
            headers=header
        )
        if res.status_code != 201:
            return JSONResponse(status_code=500, content={
                "status": "error",
                "message": "Failed to save chat history."
            })
        
        print("Successfully saved chat history.")
        return JSONResponse(status_code=200, content={
            "status": "success",
            "question": question,
            "answer": answer,
            "used_tokens": used_tokens,
            # "history": chat_history  # now returning full chat history
        })

    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e)
        })
    finally:
        if client.is_connected():
            client.close()


import asyncio
if __name__ == "__main__":
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzYwMDczNzk5LCJpYXQiOjE3NTc0ODE3OTksImp0aSI6ImM4NjAzNjU1NmNkZjQwZjdiYzFhYzc5MWE3NWU3MjAwIiwidXNlcl9pZCI6IjcifQ.Q0_AwIaCzvTfTi17XngEbmBBlJOx-An3HkQRetnM3Xg" 
    org = "HomeCare"
    q = "What is the privacy policy?"
    asyncio.run(ask_doc_bot(q, org, token))
