import json
from app.config import OPENAI_API_KEY
from app.services.policy_vector_service import policy_vector_service

from openai import OpenAI
import re
import asyncio
from typing import Dict, List, Optional

openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Constants for maximum capability
GPT4_TURBO_MODEL = "gpt-4-turbo-2024-04-09"  # Latest GPT-4 Turbo with 128k context
MAX_OUTPUT_TOKENS = 4096  # Maximum output tokens for GPT-4 Turbo
MAX_CONTEXT_TOKENS = 120000  # Leave room for output tokens
WORDS_PER_PAGE = 250  # Standard document page length
TOKENS_PER_WORD = 1.33  # Average tokens per word


def estimate_token_count(text: str) -> int:
    """More accurate token estimation for GPT-4"""
    return int(len(text) / 3.5)  # GPT-4 specific ratio

def estimate_word_count(text: str) -> int:
    """Accurate word count estimation"""
    return len(text.split())

def calculate_pages(word_count: int) -> float:
    """Calculate number of pages based on word count"""
    return word_count / WORDS_PER_PAGE

async def generate_section_content(section_title: str, section_requirements: str, 
                                 super_admin_law: str, title: str, context: str,
                                 target_words: int) -> str:
    """Generate individual section content with maximum detail"""
    
    prompt = f"""
You are an expert Australian government policy writer. Generate a comprehensive, detailed section for a formal government policy document.

SECTION REQUIREMENTS:
• Section: {section_title}
• Target Length: {target_words} words for this section
• Requirements: {section_requirements}

CRITICAL INSTRUCTIONS:
• Write EXACTLY {target_words} words for this section
• Use professional, formal government policy language
• Include comprehensive detail, examples, and procedures
• Reference relevant legal frameworks from the provided context
• Use subsections (numbered 1.1, 1.2, etc.) where appropriate
• Include specific procedural steps, compliance requirements, and examples
• Be thorough and comprehensive - this is for a formal government policy

FORMATTING:
• Start with the section number and title (e.g., "3.1 {section_title}")
• Use clear subsection numbering
• Include detailed paragraphs of 100-200 words each
• Ensure professional, authoritative tone throughout

Policy Context:
Title: {title}
Context: {context}

Legal Framework: {super_admin_law[:15000]}

Generate ONLY the section content with exactly {target_words} words. Be comprehensive and detailed.
"""

    response = openai_client.chat.completions.create(
        model=GPT4_TURBO_MODEL,
        messages=[
            {"role": "system", "content": "You are a senior Australian government policy writer. Write comprehensive, detailed policy sections with exact word count requirements. Use formal, authoritative language with extensive detail and examples."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_tokens=MAX_OUTPUT_TOKENS
    )
    
    return response.choices[0].message.content.strip()

async def generate_comprehensive_policy_structure(target_pages: int) -> List[Dict]:
    """Generate a comprehensive policy structure for maximum length policies"""
    target_words = target_pages * WORDS_PER_PAGE
    
    if target_pages <= 10:
        # Standard policy structure (up to 10 pages)
        return [
            {"title": "Executive Summary", "words": int(target_words * 0.05), "requirements": "Comprehensive overview, key points, scope"},
            {"title": "Introduction and Purpose", "words": int(target_words * 0.08), "requirements": "Detailed background, objectives, regulatory context"},
            {"title": "Scope and Application", "words": int(target_words * 0.07), "requirements": "Who, what, when, where this applies, detailed coverage"},
            {"title": "Legal Framework and Authority", "words": int(target_words * 0.12), "requirements": "All relevant legislation, regulations, powers, enforcement authority"},
            {"title": "Definitions and Key Terms", "words": int(target_words * 0.08), "requirements": "Comprehensive glossary with detailed explanations"},
            {"title": "Policy Requirements and Standards", "words": int(target_words * 0.25), "requirements": "Detailed requirements, standards, specifications, multiple subsections"},
            {"title": "Compliance Procedures", "words": int(target_words * 0.15), "requirements": "Step-by-step procedures, documentation requirements, timelines"},
            {"title": "Monitoring and Enforcement", "words": int(target_words * 0.10), "requirements": "Audit procedures, penalties, enforcement mechanisms"},
            {"title": "Implementation Guidelines", "words": int(target_words * 0.07), "requirements": "Practical implementation steps, timelines, resources"},
            {"title": "Review and Amendment Process", "words": int(target_words * 0.03), "requirements": "Review cycles, amendment procedures, stakeholder consultation"}
        ]
    else:
        # Extended structure for 10+ pages
        return [
            {"title": "Executive Summary", "words": int(target_words * 0.04), "requirements": "Comprehensive overview, key findings, recommendations"},
            {"title": "Introduction and Background", "words": int(target_words * 0.06), "requirements": "Historical context, problem statement, need for policy"},
            {"title": "Purpose and Objectives", "words": int(target_words * 0.05), "requirements": "Specific goals, outcomes, success metrics"},
            {"title": "Scope and Application", "words": int(target_words * 0.06), "requirements": "Detailed coverage, inclusions, exclusions, jurisdictional scope"},
            {"title": "Legal and Regulatory Framework", "words": int(target_words * 0.10), "requirements": "Comprehensive legal basis, statutory powers, regulatory context"},
            {"title": "Definitions and Terminology", "words": int(target_words * 0.07), "requirements": "Extensive glossary, technical terms, legal definitions"},
            {"title": "Policy Principles and Standards", "words": int(target_words * 0.12), "requirements": "Core principles, quality standards, performance criteria"},
            {"title": "Detailed Requirements and Specifications", "words": int(target_words * 0.18), "requirements": "Comprehensive requirements, technical specifications, detailed procedures"},
            {"title": "Compliance and Assessment Procedures", "words": int(target_words * 0.10), "requirements": "Assessment methods, compliance verification, documentation"},
            {"title": "Implementation Framework", "words": int(target_words * 0.08), "requirements": "Implementation phases, timelines, resource requirements"},
            {"title": "Monitoring and Evaluation", "words": int(target_words * 0.06), "requirements": "Performance monitoring, evaluation criteria, reporting requirements"},
            {"title": "Enforcement and Penalties", "words": int(target_words * 0.05), "requirements": "Enforcement mechanisms, penalty framework, appeals process"},
            {"title": "Stakeholder Engagement", "words": int(target_words * 0.03), "requirements": "Consultation processes, stakeholder roles, communication strategies"}
        ]

async def generate_ultra_comprehensive_policy(title: str, context: str, version: str = None, 
                                            target_pages: int = 30) -> dict:
    """
    Generate ultra-comprehensive policies up to 40 pages using GPT-4 Turbo's maximum capabilities.
    Uses section-by-section generation for maximum quality and length.
    """
    try:
        target_words = target_pages * WORDS_PER_PAGE
        
        print(f"Generating {target_pages}-page policy ({target_words} words)...")
        
        # Step 1: Get comprehensive legal context
        query = f"{title} {context}"
        super_admin_law_content = await policy_vector_service.get_super_admin_laws_for_generation(
            query=query,
            version=version,
            limit=50  # Maximum relevant laws
        )
        
        if not super_admin_law_content or "No laws found" in super_admin_law_content:
            return {
                "status": "error",
                "message": "Insufficient legal context found in vector database",
                "policy": None,
                "metadata": {"target_pages": target_pages, "target_words": target_words}
            }
        
        # Step 2: Generate policy structure
        policy_structure = await generate_comprehensive_policy_structure(target_pages)
        
        # Step 3: Generate table of contents
        toc_prompt = f"""
Generate a comprehensive Table of Contents for a {target_pages}-page Australian government policy document.

Policy Title: {title}
Context: {context}
Target Pages: {target_pages}
Structure: {[s['title'] for s in policy_structure]}

Create a detailed, professional table of contents with:
- Main sections (1., 2., 3., etc.)
- Subsections (1.1, 1.2, etc.)
- Sub-subsections where appropriate (1.1.1, 1.1.2, etc.)
- Page number placeholders
- Professional government document formatting

Format as a complete table of contents suitable for a formal government policy document.
"""
        
        toc_response = openai_client.chat.completions.create(
            model=GPT4_TURBO_MODEL,
            messages=[
                {"role": "system", "content": "Generate professional government document table of contents with comprehensive section structure."},
                {"role": "user", "content": toc_prompt}
            ],
            temperature=0.1,
            max_tokens=2000
        )
        
        table_of_contents = toc_response.choices[0].message.content.strip()
        
        # Step 4: Generate each section individually for maximum detail
        policy_sections = []
        total_generated_words = 0
        
        print("Generating sections:")
        for i, section in enumerate(policy_structure, 1):
            print(f"  Generating Section {i}: {section['title']} ({section['words']} words)...")
            
            section_content = await generate_section_content(
                section_title=f"{i}. {section['title']}",
                section_requirements=section['requirements'],
                super_admin_law=super_admin_law_content,
                title=title,
                context=context,
                target_words=section['words']
            )
            
            section_word_count = estimate_word_count(section_content)
            total_generated_words += section_word_count
            
            policy_sections.append({
                "section_number": i,
                "title": section['title'],
                "content": section_content,
                "word_count": section_word_count,
                "target_words": section['words']
            })
            
            print(f"    Generated: {section_word_count} words (target: {section['words']})")
            
            # Small delay to respect rate limits
            await asyncio.sleep(0.5)
        
        # Step 5: Compile final policy document
        policy_document = f"""
{table_of_contents}

{"="*80}

"""
        
        for section in policy_sections:
            policy_document += f"\n{section['content']}\n\n"
            policy_document += "="*60 + "\n\n"
        
        final_word_count = estimate_word_count(policy_document)
        final_pages = calculate_pages(final_word_count)
        
        print(f"Policy generation complete!")
        print(f"Final word count: {final_word_count} (target: {target_words})")
        print(f"Final page count: {final_pages:.1f} (target: {target_pages})")
        
        return {
            "status": "success",
            "policy": policy_document,
            "metadata": {
                "title": title,
                "version": version or "1.0",
                "target_pages": target_pages,
                "target_words": target_words,
                "actual_words": final_word_count,
                "actual_pages": round(final_pages, 1),
                "achievement_ratio": f"{(final_word_count/target_words)*100:.1f}%",
                "page_achievement": f"{(final_pages/target_pages)*100:.1f}%",
                "sections_generated": len(policy_sections),
                "law_context_length": len(super_admin_law_content),
                "generation_method": "section-by-section",
                "model_used": GPT4_TURBO_MODEL,
                "section_breakdown": [
                    {
                        "section": s['title'],
                        "target_words": s['target_words'],
                        "actual_words": s['word_count'],
                        "achievement": f"{(s['word_count']/s['target_words'])*100:.1f}%"
                    } for s in policy_sections
                ]
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error generating ultra-comprehensive policy: {str(e)}",
            "policy": None,
            "metadata": {
                "target_pages": target_pages,
                "target_words": target_words,
                "error_details": str(e)
            }
        }

# Enhanced version with alternative approaches
async def generate_policy_json(title: str, context: str, super_admin_law: str = None, 
                             target_words: int = 3000, max_tokens: int = MAX_OUTPUT_TOKENS) -> str:
    """
    Enhanced single-step generation using GPT-4 Turbo's maximum capabilities
    """
    if not super_admin_law:
        query = f"{title} {context}"
        super_admin_law = await policy_vector_service.get_super_admin_laws_for_generation(
            query=query,
            limit=40
        )
    
    # Calculate target pages for context
    target_pages = calculate_pages(target_words)
    
    prompt = f"""
You are a senior Australian government policy writer tasked with creating a comprehensive {target_pages}-page ({target_words} words) government policy document.

CRITICAL REQUIREMENTS:
• Generate EXACTLY {target_words} words ({target_pages} pages)
• Use GPT-4 Turbo's full capability for maximum comprehensive detail
• Every section must be extensively detailed with examples, procedures, and specifications
• Include comprehensive subsections and sub-subsections
• Reference and integrate the provided legal framework throughout
• Use professional government policy language and structure

DOCUMENT STRUCTURE (target {target_words} words total):
1. TABLE OF CONTENTS (detailed, multi-level)
2. EXECUTIVE SUMMARY (400-500 words)
3. INTRODUCTION & BACKGROUND ({int(target_words * 0.08)} words)
4. PURPOSE & OBJECTIVES ({int(target_words * 0.06)} words)
5. SCOPE & APPLICATION ({int(target_words * 0.08)} words)
6. LEGAL & REGULATORY FRAMEWORK ({int(target_words * 0.12)} words)
7. DEFINITIONS & TERMINOLOGY ({int(target_words * 0.10)} words)
8. POLICY REQUIREMENTS & STANDARDS ({int(target_words * 0.25)} words - MULTIPLE DETAILED SUBSECTIONS)
9. COMPLIANCE PROCEDURES ({int(target_words * 0.12)} words)
10. IMPLEMENTATION FRAMEWORK ({int(target_words * 0.08)} words)
11. MONITORING & ENFORCEMENT ({int(target_words * 0.07)} words)
12. REVIEW & AMENDMENT ({int(target_words * 0.04)} words)

WRITING INSTRUCTIONS:
• Each section must be comprehensive with detailed subsections
• Include practical examples, step-by-step procedures, and case studies
• Use extensive detail in compliance requirements and technical specifications
• Reference specific legal provisions and regulatory requirements
• Include comprehensive definitions and explanations
• Use formal government document structure and language
• Ensure each paragraph is substantial (150-300 words minimum)

Policy Details:
Title: {title}
Context: {context}
Legal Framework: {super_admin_law}

Generate the complete {target_words}-word policy document with maximum detail and comprehensiveness.
"""
    
    response = openai_client.chat.completions.create(
        model=GPT4_TURBO_MODEL,
        messages=[
            {"role": "system", "content": f"You are an expert Australian government policy writer. Generate comprehensive {target_words}-word policy documents using maximum detail and formal government structure. Use GPT-4 Turbo's full capabilities for extensive, detailed content."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_tokens=max_tokens
    )
    
    content = response.choices[0].message.content.strip()
    word_count = estimate_word_count(content)
    print(f"Single-step generation: {word_count} words (target: {target_words})")
    
    return content

async def generate_policy_with_vector_laws(title: str, context: str, version: str = None, 
                                         target_words: int = 7500, approach: str = "multi-step") -> dict:
    """
    Enhanced policy generation with multiple approaches for maximum length capability.
    
    Args:
        approach: "single-step" for up to ~10 pages, "multi-step" for 10+ pages
        target_words: Target word count (default 7500 = ~30 pages)
    """
    
    target_pages = calculate_pages(target_words)
    
    if approach == "multi-step" or target_pages > 10:
        # Use section-by-section generation for maximum length
        return await generate_ultra_comprehensive_policy(title, context, version, int(target_pages))
    else:
        # Use enhanced single-step generation
        try:
            query = f"{title} {context}"
            super_admin_law_content = await policy_vector_service.get_super_admin_laws_for_generation(
                query=query,
                version=version,
                limit=40
            )
            
            if not super_admin_law_content or "No laws found" in super_admin_law_content:
                return {
                    "status": "error",
                    "message": "No super admin laws found in vector database",
                    "policy": None,
                    "metadata": {"target_words": target_words, "target_pages": target_pages}
                }
            
            # Manage context size for GPT-4 Turbo
            law_tokens = estimate_token_count(super_admin_law_content)
            if law_tokens > MAX_CONTEXT_TOKENS:
                words = super_admin_law_content.split()
                max_words = int(MAX_CONTEXT_TOKENS * 0.75)
                super_admin_law_content = ' '.join(words[:max_words]) + '\n... [Content truncated to fit context limits]'
            
            policy_content = await generate_policy_json(
                title=title,
                context=context,
                super_admin_law=super_admin_law_content,
                target_words=target_words,
                max_tokens=MAX_OUTPUT_TOKENS
            )
            
            final_word_count = estimate_word_count(policy_content)
            final_pages = calculate_pages(final_word_count)
            
            return {
                "status": "success",
                "policy": policy_content,
                "metadata": {
                    "title": title,
                    "version": version or "1.0",
                    "target_words": target_words,
                    "target_pages": target_pages,
                    "actual_words": final_word_count,
                    "actual_pages": round(final_pages, 1),
                    "achievement_ratio": f"{(final_word_count/target_words)*100:.1f}%",
                    "generation_method": "single-step-enhanced",
                    "model_used": GPT4_TURBO_MODEL,
                    "law_context_length": len(super_admin_law_content)
                }
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error in single-step generation: {str(e)}",
                "policy": None,
                "metadata": {"target_words": target_words, "target_pages": target_pages}
            }