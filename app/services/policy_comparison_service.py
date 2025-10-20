
from openai import OpenAI
import logging
from typing import List, Dict
import json
import numpy as np
from fastapi import HTTPException, UploadFile
from app.services.extract_content import extract_content_from_uploadpdf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.services.weaviate_client import get_weaviate_client



def cosine_similarity(vector_a, vector_b):
    a = np.array(vector_a)
    b = np.array(vector_b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))



def fetch_weaviate_policies(organization: str):
    try:
        client = get_weaviate_client()
        if not client.is_connected():
            client.connect()
        collection = client.collections.get(organization)
        response = collection.query.fetch_objects(limit=1000)
        return response.objects
    except Exception as e:
        return {'status': 'error', 'message': str(e)}
    finally:
        if client.is_connected():
            client.close()


def chunk_text(text: str, max_chunk_size: int = 12000, overlap: int = 500) -> List[str]:
    """Chunk large texts by characters with small overlap for LLM processing."""
    if len(text) <= max_chunk_size:
        return [text]
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


async def summarize_large_text(openai_client: OpenAI, text: str, title: str) -> str:
    """Fast summarization with parallel chunk processing."""
    if not text:
        return ""
    
    # Reduce chunk size and overlap for speed
    chunks = chunk_text(text, max_chunk_size=8000, overlap=300)
    
    if len(chunks) == 1:
        # Single chunk - direct summary
        try:
            resp = openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Faster model
                messages=[
                    {"role": "system", "content": "Concise policy summary in 8-10 bullets."},
                    {"role": "user", "content": f"Title: {title}\n\n{chunks[0]}"}
                ],
                temperature=0.1,
                max_tokens=800
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"Summary failed: {str(e)}")
            return text[:3000]
    
    # Multiple chunks - parallel processing
    async def summarize_chunk(idx: int, chunk: str) -> str:
        try:
            resp = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Extract key points in 4-6 bullets."},
                    {"role": "user", "content": f"{title} Part {idx+1}:\n{chunk}"}
                ],
                temperature=0.1,
                max_tokens=500
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            return chunk[:1000]
    
    # Process chunks in parallel
    tasks = [summarize_chunk(i, chunk) for i, chunk in enumerate(chunks)]
    part_summaries = await asyncio.gather(*tasks)
    
    # Quick final combination
    combined = "\n\n".join(part_summaries)
    if len(combined) <= 4000:
        return combined
    
    # Final compression if needed
    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Combine into 8-10 key bullets."},
                {"role": "user", "content": f"{title}:\n{combined}"}
            ],
            temperature=0.1,
            max_tokens=800
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return combined[:4000]


def fetch_weaviate_full_text(organization: str) -> str:
    """Concatenate full text from all Weaviate policy objects (may be large)."""
    objects = fetch_weaviate_policies(organization)
    texts: List[str] = []
    for obj in objects:
        title = obj.properties.get("title", "Policy")
        text = obj.properties.get("text", "")
        if text:
            texts.append(f"Title: {title}\n{text}")
    return "\n\n\n".join(texts)



async def extract_pdf_content(file: UploadFile):
    try:
        await file.seek(0)
        text, title = await extract_content_from_uploadpdf(file)
        if not text or not text.strip():
            raise HTTPException(
                status_code=400,
                detail="No text could be extracted from the PDF."
            )
        return text.strip(), title or "Untitled Document"
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to process PDF: {str(e)}"
        )


async def compare_summaries_with_llm(openai_client: OpenAI, pdf_summary: str, weaviate_summary: str) -> Dict[str, str]:
    """Use LLM to compare two brief summaries and return alignment verdict and reasoning."""
    prompt = (
        "You will compare two brief summaries (A: Uploaded PDF, B: Stored Policies).\n"
        "Decide whether they are aligned overall (ALIGNED or NOT_ALIGNED) and provide a short reasoning (max 6 lines).\n"
        "Consider scope, obligations, processes, and standards.\n\n"
        f"Summary A (PDF):\n{pdf_summary}\n\n"
        f"Summary B (Policies):\n{weaviate_summary}\n\n"
        "Return strict JSON: {\n  \"alignment_status\": \"ALIGNED|NOT_ALIGNED\",\n  \"reasoning\": \"...\"\n}"
    )
    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a precise policy analyst. Return strict JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=1500,
        )
        content = resp.choices[0].message.content.strip()
        obj = json.loads(content)
        status = obj.get("alignment_status", "UNKNOWN")
        reasoning = obj.get("reasoning", "")
        return {"alignment_status": status, "reasoning": reasoning}
    except Exception as e:
        logger.warning(f"Summary comparison failed: {str(e)}")
        return {"alignment_status": "UNKNOWN", "reasoning": "Comparison failed."}


async def detect_conflicts_or_differences(openai_client: OpenAI, pdf_summary: str, weaviate_summary: str) -> Dict[str, object]:
    """Use LLM to extract direct conflicts if any; otherwise list key differences. Returns JSON."""
    prompt = (
        "Read Summary A (PDF) and Summary B (Policies).\n"
        "1) If there are any DIRECT CONFLICTS (requirements that cannot both be true), list 1-8 concise conflict items.\n"
        "2) If there are NO direct conflicts, list 3-8 concise differences (scope, wording, thresholds, processes) and explicitly say no direct conflicts.\n"
        "Keep each item short (one sentence).\n\n"
        f"Summary A (PDF):\n{pdf_summary}\n\n"
        f"Summary B (Policies):\n{weaviate_summary}\n\n"
        "Return strict JSON only in this schema:\n"
        "{\n  \"direct_conflict\": true|false,\n  \"conflicts\": [\"...\"],\n  \"differences\": [\"...\"],\n  \"note\": \"If false, mention there is no direct conflict.\"\n}"
    )
    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a precise compliance analyst. Return strict JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=1500,
        )
        content = resp.choices[0].message.content.strip()
        obj = json.loads(content)
        return {
            "direct_conflict": bool(obj.get("direct_conflict", False)),
            "conflicts": obj.get("conflicts", [])[:8],
            "differences": obj.get("differences", [])[:8],
            "note": obj.get("note", "")
        }
    except Exception as e:
        logger.warning(f"Conflict/difference detection failed: {str(e)}")
        return {
            "direct_conflict": False,
            "conflicts": [],
            "differences": [],
            "note": "Analysis failed."
        }


async def generate_contradiction_paragraph(openai_client: OpenAI, pdf_summary: str, weaviate_summary: str) -> str:
    """Produce a single concise paragraph summarizing contradictions; if none, state no direct conflict and key differences."""
    prompt = (
        "Compose ONE concise paragraph (4-7 sentences) that summarizes any DIRECT contradictions between: \n"
        "A) the uploaded PDF summary and B) the main policies. \n"
        "If there are NO direct contradictions, explicitly state that and highlight the main differences in scope, thresholds, or processes, still within one paragraph. \n"
        "Do NOT mention any platform or system names (e.g., Weaviate). \n"
        "Avoid lists. Be specific but brief.\n\n"
        f"Summary A (PDF):\n{pdf_summary}\n\n"
        f"Summary B (Policies):\n{weaviate_summary}"
    )
    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You write precise compliance summaries in a single paragraph."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=700,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"Contradiction paragraph generation failed: {str(e)}")
        return "Analysis unavailable."



from app.config import OPENAI_API_KEY
from openai import OpenAI

async def cosine_similarity_test(file: UploadFile, organization: str = "GlobalLaw"):
    full_text, _title = await extract_pdf_content(file)
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        max_chars = 8192 * 3
        if len(full_text) > max_chars:
            embedding_text = (
                full_text[:max_chars // 2]
                + "\n\n[...CONTENT_TRUNCATED...]\n\n"
                + full_text[-max_chars // 2:]
            )
        else:
            embedding_text = full_text
        embedding_response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=embedding_text
        )
        uploaded_embedding = embedding_response.data[0].embedding
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate embedding: {str(e)}"
        )
    policies = fetch_weaviate_policies(organization)
    similarities = []
    for policy_obj in policies:
        policy_embedding = policy_obj.properties.get("embedding", [])
        if policy_embedding:
            similarity_score = cosine_similarity(uploaded_embedding, policy_embedding)
            similarities.append(similarity_score)
    if not similarities:
        raise HTTPException(
            status_code=500,
            detail="No valid embeddings found for comparison"
        )
    max_similarity = max(similarities)
    alignment_percent = round(max_similarity * 100, 2)
    not_alignment_percent_cosine = round(100 - alignment_percent, 2)
    return {
        "not_alignment_percent": not_alignment_percent_cosine
    }


import asyncio

async def combined_alignment_analysis(file: UploadFile, organization: str = "GlobalLaw") -> Dict[str, object]:
    """Fast parallel analysis with optimized LLM calls."""
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    
    # Parallel execution of PDF extraction and Weaviate fetch
    pdf_task = extract_pdf_content(file)
    weaviate_task = asyncio.create_task(asyncio.to_thread(fetch_weaviate_full_text, organization))
    
    full_text, pdf_title = await pdf_task
    weaviate_full_text = await weaviate_task
    
    # Parallel summarization
    pdf_summary_task = summarize_large_text(openai_client, full_text, pdf_title)
    weaviate_summary_task = summarize_large_text(openai_client, weaviate_full_text, "Main Policies")
    
    pdf_summary, weaviate_summary = await asyncio.gather(pdf_summary_task, weaviate_summary_task)
    
    # Single LLM call for both conflict detection and paragraph generation
    combined_prompt = (
        f"Analyze these summaries for conflicts and generate response:\n"
        f"PDF: {pdf_summary}\n\nPolicies: {weaviate_summary}\n\n"
        f"Return JSON: {{\"direct_conflict\": true/false, \"conflicts\": [...], "
        f"\"differences\": [...], \"paragraph\": \"single paragraph summary\"}}"
    )
    
    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4o-mini",  # Faster model
            messages=[
                {"role": "system", "content": "Return strict JSON only."},
                {"role": "user", "content": combined_prompt}
            ],
            temperature=0.1,
            max_tokens=1000
        )
        result = json.loads(resp.choices[0].message.content.strip())
        
        # Calculate score
        if result.get("direct_conflict", False):
            conflict_count = len(result.get("conflicts", []))
            not_alignment_percent = min(85 + (conflict_count * 5), 100)
        else:
            difference_count = len(result.get("differences", []))
            not_alignment_percent = min(10 + (difference_count * 5), 35)
        
        return {
            "not_alignment_percent": round(not_alignment_percent, 1),
            "contradiction_paragraph": result.get("paragraph", "Analysis unavailable.")
        }
    except Exception as e:
        logger.warning(f"Combined analysis failed: {str(e)}")
        return {
            "not_alignment_percent": 25.0,
            "contradiction_paragraph": "Analysis unavailable due to processing error."
        }


async def summarize_pdf_and_policies(file: UploadFile, organization: str = "PolicyEmbeddings") -> Dict[str, str]:
    """Return brief summaries for the uploaded PDF and all Weaviate policies."""
    # Extract and summarize PDF
    full_text, pdf_title = await extract_pdf_content(file)
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    pdf_summary = await summarize_large_text(openai_client, full_text, pdf_title)

    # Fetch, concatenate, and summarize Weaviate texts
    weaviate_full_text = fetch_weaviate_full_text(organization)
    weaviate_summary = await summarize_large_text(openai_client, weaviate_full_text, "Main Policies")

    return {
        "pdf_summary": pdf_summary,
        "weaviate_summary": weaviate_summary,
    }
