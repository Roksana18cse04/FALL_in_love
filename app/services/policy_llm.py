import json
from app.config import OPENAI_API_KEY

from openai import OpenAI

openai_client = OpenAI(api_key=OPENAI_API_KEY)



async def generate_policy_json(context: str, super_admin_law: str) -> str:
    """
    Use LLM to generate a standard, Australia-compliant company/organization policy in JSON format, using super admin law as context.
    """
    prompt = f"""
ou are an expert policy writer for an Australian government regulatory body. Your task is to generate a comprehensive public-facing policy document that explains a specific regulatory process. Given the legal framework from a 'Super Admin' and the operational context from an 'Admin', generate a complete, standard, and compliant policy in JSON format.
The policy must:
• Be written in clear, professional, and accessible English, suitable for providers, organizations, and the public.
• Be structured as a formal public policy document, not an internal company policy.
• Adhere strictly to the provided Australian legal framework and operational context.
• Begin with a title, version number, and effective date.
• Include a detailed table of contents.
• Structure the main body using a numbered hierarchy (e.g., 1., 1.1, 1.1.1).
• Include key sections that explain the "how" and "why" of the regulatory process, modelled on the example's structure:
    ◦ Purpose of this policy: A clear statement explaining what the policy covers and for whom.
    ◦ Overview of the Commission/Regulator: Briefly describe the regulator's role and mission.
    ◦ Regulatory Approach: Explain the principles guiding the regulatory activities, referencing key strategies and legislation.
    ◦ Legislative Framework: List the specific Acts and Rules under which the regulator operates.
    ◦ Detailed Process Sections: Break down the core processes into logical, numbered sections (e.g., 'Initial Registration', 'Renewing Registration', 'Changes to Registration').
    ◦ Key Concepts and Models: Explain any specific models or frameworks used (e.g., 'Registration model', 'Supervision model').
    ◦ Definitions: Reference where key terms are defined, such as an external glossary

Super Admin Law Context: {super_admin_law}
Admin Policy Context: {context}

Generated policy must be at least 6000 words.

Output ONLY the JSON object, no explanations or markdown.
"""
    response = openai_client.chat.completions.create(
    model="gpt-4.1",  # Use GPT-4.1 for enhanced capabilities
    messages=[
        {"role": "system", "content": "You are a legal policy generator for Australian organizations. Write policies in professional, detailed, corporate language."},
        {"role": "user", "content": prompt}
    ],
    temperature=0.2,
    max_tokens=32768  # GPT-4.1 supports up to 32,768 output tokens
)
    # Extract JSON from response
    content = response.choices[0].message.content.strip()
    # Validate JSON
    try:
        policy_obj = json.loads(content)
        return json.dumps(policy_obj, indent=2)
    except Exception:
        # If not valid JSON, return as-is
        return content


