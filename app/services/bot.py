import openai
from app.services.weaviate_client import client
from weaviate.classes.query import MetadataQuery
from fastapi.responses import JSONResponse
from app.config import OPENAI_API_KEY
from openai import OpenAI

# ✅ Global variable for chat history (short-term memory)
chat_history = []

openai_client = OpenAI(api_key=OPENAI_API_KEY)
class_name = "PolicyDocuments"

def build_context_from_weaviate_results(query_text, limit=5, alpha=0.5):
    if not client.is_connected():
        client.connect()

    collection = client.collections.get(class_name)

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
        props_text = "\n".join(f"{key}: {value}" for key, value in props.items())
        print("properties-----------", props)

        chunk = (
            f"UUID: {uuid}\n"
            # f"Score: {score}\n"
            f"Properties:\n{props_text}\n"
            "-----"
        )
        context_chunks.append(chunk)
        print("context chunk----------", context_chunks)

    context = "\n\n".join(context_chunks)
    return context.strip()

async def ask_doc_bot(question: str):
    """Ask question to GPT-4 using Weaviate context and short-term memory"""
    global chat_history  # <- use global history

    try:
        context = build_context_from_weaviate_results(question)

        system_prompt = (
            "You are a helpful assistant that answers questions based on organizational policy documents.\n"
            "Each document excerpt includes metadata: Title, Source, Created At, Last Update, UUID, and Content.\n"
            "When referencing a policy, always include the ID next to the title in this format: Title [IR-xxxxxx], where 'xxxxxx' is derived from the first 6 characters of the UUID.\n"
            "Use the metadata to answer questions about policy details, such as when it was last updated or where it is sourced from.\n"
            "If the answer is not found in the context, say 'I don't know based on the documents.'"
        )

        # Build messages: system + history + current question
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(chat_history)  # Append past conversation
        messages.append({
            "role": "user",
            "content": f"Context:\n{context}\n\nQuestion: {question}"
        })

        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.3
        )

        answer = response.choices[0].message.content.strip()

        # ✅ Update global history
        chat_history.append({"role": "user", "content": question})
        chat_history.append({"role": "assistant", "content": answer})
        
        return JSONResponse(status_code=200, content={
            "status": "success",
            "question": question,
            "answer": answer,
            "history": chat_history
        })

    except Exception as e:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": str(e)
        })
