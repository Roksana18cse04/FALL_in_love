
from openai import OpenAI
import logging
from typing import List, Dict
import json
import numpy as np
from fastapi import HTTPException, UploadFile
from app.services.extract_content import extract_content_from_pdf

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
    client = get_weaviate_client()
    if not client.is_connected():
        client.connect()
    collection = client.collections.get(organization)
    response = collection.query.fetch_objects(limit=1000)
    return response.objects


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
    """Summarize potentially large text using chunking, then compress to a brief summary."""
    if not text:
        return ""
    chunks = chunk_text(text, max_chunk_size=12000, overlap=600)
    part_summaries: List[str] = []
    for idx, chunk in enumerate(chunks):
        prompt = (
            f"You are a senior policy analyst. Provide a concise summary (6-10 bullet points) "
            f"covering key requirements, scope, processes, and compliance obligations.\n\n"
            f"Title: {title}\n"
            f"Part {idx+1} of {len(chunks)}:\n\n{chunk}"
        )
        try:
            resp = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You produce concise, accurate summaries."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=900,
            )
            part_summaries.append(resp.choices[0].message.content.strip())
        except Exception as e:
            logger.warning(f"Chunk summary failed ({idx+1}/{len(chunks)}): {str(e)}")
            part_summaries.append(chunk[:2000])
    combined = "\n\n".join(part_summaries)
    # Compress to brief summary
    try:
        final_prompt = (
            "Combine the following bullet summaries into a brief executive summary (8-12 bullets).\n"
            "Avoid redundancy; keep it crisp and precise.\n\n"
            f"Title: {title}\n\n"
            f"Summaries:\n{combined}"
        )
        final = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You produce concise, accurate summaries."},
                {"role": "user", "content": final_prompt},
            ],
            temperature=0.5,
            max_tokens=1500,
        )
        return final.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"Final summary compression failed: {str(e)}")
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
        text, title = await extract_content_from_pdf(file)
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

async def cosine_similarity_test(file: UploadFile, organization: str = "PolicyEmbeddings"):
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


async def combined_alignment_analysis(file: UploadFile, organization: str = "PolicyEmbeddings") -> Dict[str, object]:
    """Run cosine similarity, summarize both sides, and return a single contradiction paragraph."""
    # Cosine percent
    cosine_result = await cosine_similarity_test(file, organization)

    # Extract full PDF text
    full_text, pdf_title = await extract_pdf_content(file)

    # Fetch Weaviate full texts
    weaviate_full_text = fetch_weaviate_full_text(organization)

    # LLM summarize and compare
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    pdf_summary = await summarize_large_text(openai_client, full_text, pdf_title)
    weaviate_summary = await summarize_large_text(openai_client, weaviate_full_text, "Main Policies")
    contradiction_paragraph = await generate_contradiction_paragraph(openai_client, pdf_summary, weaviate_summary)

    return {
        "not_alignment_percent": cosine_result["not_alignment_percent"],
        "contradiction_paragraph": contradiction_paragraph,
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
