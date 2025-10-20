def parse_object_key(object_key: str):
    """
    Extract category, document_type, and filename from object_key
    Example: "AI/policy/privacy_confidentiality_information_governance/provider-registration-policy.pdf"
    Returns: category, document_type, filename
    """
    parts = object_key.split('/')
    
    if len(parts) < 4:
        raise ValueError("Invalid object_key format")
    
    # Skip "AI" prefix
    document_type = parts[1]  # "policy"
    category = parts[2]       # "privacy_confidentiality_information_governance"
    filename = parts[3].replace('.pdf', '').replace('-', ' ').title()  # "Provider Registration Policy"
    
    return category, document_type, filename