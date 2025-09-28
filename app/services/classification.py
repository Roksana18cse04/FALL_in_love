import os
from app.config import OPENAI_API_KEY
from openai import AsyncOpenAI, OpenAI
import json

categories = [
    {"name": "Governance & Leadership", "value": "governance_leadership"},
    {"name": "Risk Management & Quality Improvement", "value": "risk_management_quality_improvement"},
    {"name": "Human Resources & Workforce Management", "value": "human_resources_workforce_management"},
    {"name": "Competency & Training", "value": "competency_training"},
    {"name": "Clinical Care & Support Services", "value": "clinical_care_support_services"},
    {"name": "Care Planning & Agreements", "value": "care_planning_agreements"},
    {"name": "Work Health & Safety (WHS)", "value": "work_health_safety_whs"},
    {"name": "Incident Management & Reporting", "value": "incident_management_reporting"},
    {"name": "Infection Prevention & Control", "value": "infection_prevention_control"},
    {"name": "Medication Management", "value": "medication_management"},
    {"name": "Behavior Support & Restrictive Practices", "value": "behavior_support_restrictive_practices"},
    {"name": "Emergency & Disaster Management", "value": "emergency_disaster_management"},
    {"name": "Financial Management & Procurement", "value": "financial_management_procurement"},
    {"name": "Privacy, Confidentiality & Information Governance", "value": "privacy_confidentiality_information_governance"},
    {"name": "Resident / Participant Rights & Safeguarding", "value": "resident_participant_rights_safeguarding"},
    {"name": "Feedback & Complaints Management", "value": "feedback_complaints_management"},
    {"name": "Diversity, Inclusion & Cultural Safety", "value": "diversity_inclusion_cultural_safety"},
    {"name": "Safeguarding Children & Vulnerable Persons", "value": "safeguarding_children_vulnerable_persons"},
    {"name": "Continuous Improvement & Audit Evidence", "value": "continuous_improvement_audit_evidence"},
    {"name": "Operational Registers & Logs", "value": "operational_registers_logs"},
    {"name": "Others", "value": "others"}
]

# Document types we expect (you can extend this)
document_types = [
    "policy",
    "procedure",
    "guideline",
    "standard"
]
async def classify_category(docs_summary: str):
    prompt = f"""
You are an assistant that classifies aged-care organization documents.

1. Read the document text.
2. Return:
   - The **category** from this list (choose the best match): {[c["value"] for c in categories]}

Document text:
{docs_summary}
"""
    try:
        async with AsyncOpenAI(api_key=OPENAI_API_KEY) as client:
            response = await client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You classify aged-care documents into category."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0
            )

        raw_content = response.choices[0].message.content.strip()
        print("Raw docs category classification response:", raw_content)
        category = raw_content.strip().strip('"').strip("'")

        return {"category": category, "used_tokens": response.usage.total_tokens}

    except Exception as e:
        print(f"Error during classification: {e}")
        return {"category": "others", "used_tokens": 0, "error": str(e)}



# Predict both category and document_type for Staff
async def predict_relevant_category_and_type(query: str):
    prompt = f"""
You are an assistant that helps staff find the right aged-care documents.

Given this staff query:
"{query}"

1. Suggest the most relevant **category** from the following:
{[c['value'] for c in categories]}

2. Suggest the most likely **document_type** from the following:
{document_types}.

Output strictly as JSON:
{{
  "category": "value_from_list",
  "document_type": "value_from_list"
}}
3. If unsure, use "others" for either field.
"""
    try:
        async with AsyncOpenAI(api_key=OPENAI_API_KEY) as openai_client:
            response = openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that maps staff queries to document categories and types."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0
            )
        result = json.loads(response.choices[0].message.content.strip())
        # correct json if necessary

        return {
            "category": result.get("category", "others"),
            "document_type": result.get("document_type", "others"),
            "is_document_related": not (result['category'] == "others" and result['document_type'] == "others"),
            "used_tokens": response.usage.total_tokens
        }
    except Exception as e:
        print(f"Error predicting category/type: {e}")
        return {"category": "others", "document_type": "others", "is_document_related": False, "used_tokens": 0}


if __name__=="__main__":
    text = "what is privacy policy?"
    result = predict_relevant_category_and_type(query=text)
    print(result)

    # # Example Output: {'category': 'infection_prevention_control', 'document_type': 'policy'}
    # summary = """This policy outlines the procedures for infection prevention and control within the aged care facility. It includes guidelines on hand hygiene, use of personal protective equipment (PPE), cleaning and disinfection protocols, and management of infectious diseases. The policy aims to protect residents, staff, and visitors from infections and ensure a safe environment."""
    # result = classify_category(docs_summary=summary)    
    # print(result)