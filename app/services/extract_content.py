import pdfplumber

def extract_content_from_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"

        # title generation logic
        title = pdf_path.split("/")[-1].replace(".pdf", "")
        
    return text.strip(), title