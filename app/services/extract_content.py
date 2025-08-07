import pdfplumber
import io

async def extract_content_from_pdf(file):
    try:
        # Read the contents of the file once
        contents = await file.read()

        # Wrap contents in BytesIO
        pdf_bytes = io.BytesIO(contents)

        # Try to open with pdfplumber
        text = ""
        with pdfplumber.open(pdf_bytes) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

        title = file.filename.replace(".pdf", "") if file.filename else "Unknown Document"
        return text.strip(), title

    except Exception as e:
        print(f"Error extracting PDF content: {str(e)}")
        title = file.filename.replace(".pdf", "") if file.filename else "Unknown Document"
        return "", title
