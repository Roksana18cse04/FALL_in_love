

async def formatted_content(question_type, org_context, law_context) -> str:
    # Format context based on question type
    formatted_content = ""
    
    if question_type == "POLICY":
        if org_context:
            formatted_content += "ORGANIZATION CONTEXT:\n"
            for i, doc in enumerate(org_context, 1):
                title = doc.properties.get('title', 'Unknown')
                data = doc.properties.get('data', '')
                formatted_content += f"[Org-{i}] {title}\n{data}\n\n"
        else:
            formatted_content += "NO ORGANIZATION CONTEXT AVAILABLE\n"
            formatted_content += "NOTE: No organizational documents have been uploaded yet. Provide general guidance with a disclaimer.\n\n"
    
    elif question_type == "LAW":
        if law_context:
            formatted_content += "AUSTRALIAN LAW CONTEXT:\n"
            for i, doc in enumerate(law_context, 1):
                title = doc.properties.get('title', 'Unknown')
                data = doc.properties.get('data', '')
                formatted_content += f"[Law-{i}] {title}\n{data}\n\n"
    
    elif question_type == "MIXED":
        if org_context:
            formatted_content += "=== ORGANIZATION CONTEXT ===\n"
            for i, doc in enumerate(org_context, 1):
                title = doc.properties.get('title', 'Unknown')
                data = doc.properties.get('data', '')
                formatted_content += f"[Org-{i}] {title}\n{data}\n\n"
        else:
            formatted_content += "=== NO ORGANIZATION CONTEXT ===\n"
            formatted_content += "NOTE: No organizational policies uploaded yet for this scenario.\n\n"
        
        if law_context:
            formatted_content += "=== AUSTRALIAN LAW CONTEXT ===\n"
            for i, doc in enumerate(law_context, 1):
                title = doc.properties.get('title', 'Unknown')
                data = doc.properties.get('data', '')
                formatted_content += f"[Law-{i}] {title}\n{data}\n\n"
        else:
            formatted_content += "=== NO LAW CONTEXT ===\n"
            formatted_content += "NOTE: No specific legal documents found. Use general legal knowledge.\n\n"
    
    return formatted_content
