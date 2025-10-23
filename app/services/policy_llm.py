"""
Updated policy_llm.py with inline styles and error handling fixes
"""

import json
from app.config import OPENAI_API_KEY
from app.services.policy_vector_service import PolicyVectorService
from openai import OpenAI
import re
import asyncio
from typing import Dict, List, Optional

openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Constants
GPT4_TURBO_MODEL = "gpt-4-turbo-2024-04-09"
MAX_OUTPUT_TOKENS = 4096
MAX_CONTEXT_TOKENS = 120000
WORDS_PER_PAGE = 250
TOKENS_PER_WORD = 1.33


def estimate_token_count(text: str) -> int:
    """More accurate token estimation for GPT-4"""
    return int(len(text) / 3.5)

def estimate_word_count(text: str) -> int:
    """Accurate word count estimation"""
    return len(text.split())

def calculate_pages(word_count: int) -> float:
    """Calculate number of pages based on word count"""
    return word_count / WORDS_PER_PAGE


def select_relevant_law_content(law_content: str, query: str, max_chars: int = 8000) -> str:
    """
    Select most relevant law content with improved algorithm
    """
    if not law_content:
        return "Standard regulatory framework"
    
    if len(law_content) <= max_chars:
        return law_content
    
    # Extract keywords from query
    query_keywords = [kw.lower() for kw in query.split() if len(kw) > 2]
    
    # Split into paragraphs and sentences for better granularity
    paragraphs = [p.strip() for p in law_content.split('\n\n') if p.strip()]
    
    if not paragraphs:
        # Fallback: take first max_chars
        return law_content[:max_chars] + "..."
    
    # Score paragraphs
    scored_paragraphs = []
    for para in paragraphs:
        if len(para) < 50:  # Skip very short paragraphs
            continue
            
        score = 0
        para_lower = para.lower()
        
        # Query keyword matches (higher weight)
        for keyword in query_keywords:
            score += para_lower.count(keyword) * 3
        
        # Legal importance terms
        legal_terms = ['requirement', 'compliance', 'regulation', 'standard', 'procedure', 
                      'mandatory', 'shall', 'must', 'policy', 'guideline', 'framework']
        for term in legal_terms:
            score += para_lower.count(term)
        
        # Prefer paragraphs with structure indicators
        if any(indicator in para_lower for indicator in ['section', 'article', 'clause', 'subsection']):
            score += 2
            
        scored_paragraphs.append((score, para))
    
    # Sort by relevance
    scored_paragraphs.sort(key=lambda x: x[0], reverse=True)
    
    # Select top paragraphs within character limit
    selected_content = ""
    used_chars = 0
    
    for score, para in scored_paragraphs:
        if used_chars + len(para) + 4 <= max_chars:
            selected_content += para + "\n\n"
            used_chars += len(para) + 4
        elif used_chars < max_chars * 0.8:  # If we haven't used 80% of limit, try partial
            remaining = max_chars - used_chars - 4
            if remaining > 200:  # Only if meaningful content can fit
                selected_content += para[:remaining] + "...\n\n"
                break
    
    result = selected_content.strip()
    return result if result else law_content[:max_chars] + "..."


def convert_markdown_to_inline_html(markdown_content: str) -> str:
    """
    Convert markdown to HTML with inline styles (no embedded <style> tags)
    """
    import markdown
    
    # Convert markdown to HTML
    html_content = markdown.markdown(
        markdown_content,
        extensions=['extra', 'nl2br', 'sane_lists']
    )
    
    # Define inline styles
    styles = {
        'p': 'font-family: Georgia, Times New Roman, serif; margin: 1.2em 0; font-size: 16px; line-height: 1.8; color: #333; text-align: justify;',
        'strong': 'font-weight: 700; color: #000;',
        'h1': 'font-family: Georgia, Times New Roman, serif; font-size: 32px; font-weight: 700; color: #1a1a1a; margin: 2em 0 1em 0; text-align: center; border-bottom: 3px solid #333; padding-bottom: 0.5em;',
        'h2': 'font-family: Georgia, Times New Roman, serif; font-size: 26px; font-weight: 700; color: #1a1a1a; margin: 2em 0 0.8em 0; border-bottom: 2px solid #666; padding-bottom: 0.3em;',
        'h3': 'font-family: Georgia, Times New Roman, serif; font-size: 22px; font-weight: 600; color: #2c2c2c; margin: 1.5em 0 0.6em 0;',
        'h4': 'font-family: Georgia, Times New Roman, serif; font-size: 18px; font-weight: 600; color: #333; margin: 1.2em 0 0.5em 0;',
        'ul': 'font-family: Georgia, Times New Roman, serif; margin: 1.2em 0; padding-left: 2.5em;',
        'ol': 'font-family: Georgia, Times New Roman, serif; margin: 1.2em 0; padding-left: 2.5em;',
        'li': 'font-family: Georgia, Times New Roman, serif; margin: 0.6em 0; font-size: 16px; line-height: 1.6; color: #333;',
        'blockquote': 'font-family: Georgia, Times New Roman, serif; border-left: 4px solid #ddd; padding: 1em 1em 1em 1.5em; margin: 1.5em 0; font-style: italic; color: #555; background: #f9f9f9;',
        'code': 'font-family: Courier New, monospace; background: #f4f4f4; padding: 3px 8px; border-radius: 4px; font-size: 14px;',
        'hr': 'border: none; border-top: 2px solid #ddd; margin: 3em 0;',
        'table': 'font-family: Georgia, Times New Roman, serif; width: 100%; border-collapse: collapse; margin: 1.5em 0;',
        'th': 'font-family: Georgia, Times New Roman, serif; border: 1px solid #ddd; padding: 12px; text-align: left; background-color: #f5f5f5; font-weight: 600;',
        'td': 'font-family: Georgia, Times New Roman, serif; border: 1px solid #ddd; padding: 12px; text-align: left;',
        'a': 'color: #0066cc; text-decoration: underline;',
        'em': 'font-style: italic;'
    }
    
    # Apply inline styles to each tag
    for tag, style in styles.items():
        # Replace opening tags with styled versions
        html_content = re.sub(
            f'<{tag}>', 
            f'<{tag} style="{style}">', 
            html_content
        )
        # Handle tags with existing attributes (like <a href="...">)
        html_content = re.sub(
            f'<{tag} ([^>]+)>', 
            f'<{tag} style="{style}" \\1>', 
            html_content
        )
    
    # Wrap in container div with inline styles
    container_style = 'font-family: Georgia, Times New Roman, serif; line-height: 1.8; color: #333; max-width: 900px; margin: 0 auto; padding: 20px;'
    
    return f'<div style="{container_style}">{html_content}</div>'


async def generate_policy_html(title: str, context: str, organization_type: str, target_words: int = 3000) -> dict:
    """
    Generate policy content in HTML format with inline styling (no embedded CSS)
    """
    try:
        # Get legal framework
        query = f"{title} {context}"
        super_admin_law_content = "Standard regulatory framework"
        
        try:
            vector_service = PolicyVectorService(organization_type)
            full_law_content = await vector_service.get_super_admin_laws_for_generation(
                query=query, limit=5
            )
            # Select most relevant law content based on query
            super_admin_law_content = select_relevant_law_content(
                full_law_content, query, 6000
            ) if full_law_content else "Standard regulatory framework"
            print(f"Retrieved law content: {len(full_law_content)} characters, using: {len(super_admin_law_content)} characters")
        except Exception as e:
            print(f"Vector service error (using fallback): {e}")
        
        prompt = f"""
You are a professional policy writer. Create a comprehensive policy document with the following structure:

1. **Executive Summary** (2-3 paragraphs)
2. **Purpose & Objectives** (bullet points)
3. **Scope & Application** (detailed sections)
4. **Policy Requirements** (numbered sections with subsections)
5. **Compliance Procedures** (step-by-step)
6. **Implementation** (timeline and responsibilities)

Title: {title}
Context: {context}
Target Length: {target_words} words

Format Requirements:
- Use markdown formatting (##, ###, -, *, 1., etc.)
- Include bullet points and numbered lists
- Use bold text for emphasis (**text**)
- Create clear section headers
- Write in professional, formal tone
- Include specific procedures and requirements

IMPORTANT: Ensure the policy STRICTLY COMPLIES with the legal framework provided below. Do not contradict any legal requirements.

Legal Framework: {super_admin_law_content[:2000] if super_admin_law_content else 'Standard regulatory framework'}

Generate the complete policy document in markdown format that fully aligns with the above legal framework.
"""
        
        response = openai_client.chat.completions.create(
            model=GPT4_TURBO_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert policy writer. Generate comprehensive, professional policy documents in markdown format with proper structure, bullet points, and formatting."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=4000
        )
        used_tokens = response.usage.total_tokens if response.usage else 0
        markdown_content = response.choices[0].message.content.strip()
        
        # Convert markdown to HTML with inline styles
        styled_html = convert_markdown_to_inline_html(markdown_content)
        
        final_word_count = estimate_word_count(markdown_content)
        
        print(f"Policy generation complete with inline styles! Word count: {final_word_count}")
        
        return {
            "status": "success",
            "generated_content": styled_html,
            "word_count": final_word_count,
            "success": True,
            "error_message": None,
            "used_tokens": used_tokens
        }
        
    except Exception as e:
        print(f"Error in generate_policy_html: {str(e)}")
        return {
            "status": "error",
            "generated_content": None,
            "word_count": 0,
            "success": False,
            "error_message": str(e),
            "original_context": f"{title} - {context}"
        }


async def generate_policy_with_vector_laws(organization_type: str, title: str, context: str, 
                                         version: str = None, target_words: int = 7500, 
                                         approach: str = "single-step") -> dict:
    """
    Enhanced policy generation with inline styles
    """
    try:
        query = f"{title} {context}"
        super_admin_law_content = "Standard regulatory framework"
        
        try:
            vector_service = PolicyVectorService(organization_type)
            full_law_content = await vector_service.get_super_admin_laws_for_generation(
                query=query,
                version=version,
                limit=5
            )
            # Select most relevant law content based on query
            super_admin_law_content = select_relevant_law_content(
                full_law_content, query, 8000
            ) if full_law_content else "Standard regulatory framework"
            print(f"Retrieved law content: {len(full_law_content)} characters, using: {len(super_admin_law_content)} characters")
        except Exception as e:
            print(f"Vector service error (using fallback): {e}")
        
        # Manage context size
        law_tokens = estimate_token_count(super_admin_law_content)
        if law_tokens > MAX_CONTEXT_TOKENS:
            words = super_admin_law_content.split()
            max_words = int(MAX_CONTEXT_TOKENS * 0.75)
            super_admin_law_content = ' '.join(words[:max_words]) + '\n... [Content truncated]'
        
        # Generate markdown content
        prompt = f"""
You are a professional policy writer. Create a comprehensive policy document with the following structure:

1. **Executive Summary** (2-3 paragraphs)
2. **Purpose & Objectives** (bullet points)
3. **Scope & Application** (detailed sections)
4. **Policy Requirements** (numbered sections with subsections)
5. **Compliance Procedures** (step-by-step)
6. **Implementation** (timeline and responsibilities)

Title: {title}
Context: {context}
Target Length: {target_words} words

Format Requirements:
- Use markdown formatting (##, ###, -, *, 1., etc.)
- Include bullet points and numbered lists
- Use bold text for emphasis (**text**)
- Create clear section headers
- Write in professional, formal tone
- Include specific procedures and requirements

IMPORTANT: Ensure the policy STRICTLY COMPLIES with the legal framework provided below. Do not contradict any legal requirements.

Legal Framework: {super_admin_law_content}

Generate the complete policy document in markdown format that fully aligns with the above legal framework.
"""
        
        response = openai_client.chat.completions.create(
            model=GPT4_TURBO_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert policy writer. Generate comprehensive, professional policy documents in markdown format."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=4000
        )
        
        markdown_content = response.choices[0].message.content.strip()
        
        # Convert to HTML with inline styles
        styled_html = convert_markdown_to_inline_html(markdown_content)
        
        final_word_count = estimate_word_count(markdown_content)
        final_pages = calculate_pages(final_word_count)
        
        return {
            "status": "success",
            "policy": styled_html,
            "metadata": {
                "title": title,
                "version": version or "1.0",
                "target_words": target_words,
                "actual_words": final_word_count,
                "actual_pages": round(final_pages, 1),
                "achievement_ratio": f"{(final_word_count/target_words)*100:.1f}%",
                "generation_method": "single-step-inline-styles",
                "model_used": GPT4_TURBO_MODEL,
                "law_context_length": len(super_admin_law_content)
            }
        }
        
    except Exception as e:
        print(f"Error in generate_policy_with_vector_laws: {str(e)}")
        return {
            "status": "error",
            "message": f"Error in policy generation: {str(e)}",
            "policy": None,
            "metadata": {"target_words": target_words}
        }