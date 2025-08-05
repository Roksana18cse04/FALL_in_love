import pdfplumber
import fitz  # PyMuPDF
import io

async def extract_content_from_pdf(file):
    title = file.filename.replace(".pdf", "") if file.filename else "Unknown Document"
    
    try:
        # Read file once
        contents = await file.read()
        pdf_bytes = io.BytesIO(contents)

        # Try extracting with pdfplumber
        text = ""
        with pdfplumber.open(pdf_bytes) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

        if text.strip():
            return text.strip(), title
        else:
            raise ValueError("No text extracted by pdfplumber")

    except Exception as e:
        print(f"pdfplumber failed: {str(e)}. Trying fallback with PyMuPDF...")

        try:
            # Reset the stream for PyMuPDF
            pdf_bytes.seek(0)
            doc = fitz.open(stream=pdf_bytes.read(), filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
            return text.strip(), title
        except Exception as e2:
            print(f"PyMuPDF also failed: {str(e2)}")
            return "", title
