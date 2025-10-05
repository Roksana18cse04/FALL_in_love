import pdfplumber
import os
from fastapi import UploadFile

async def extract_content_from_pdf(file_path: str):
    text = ""
    title = os.path.basename(file_path)
    print(f"Summarizing the {title}...........")

    try:
        # Open PDF with pdfplumber
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

        return text.strip(), title

    except Exception as e:
        print(f"Error extracting PDF content: {str(e)}")
        return "", title

async def extract_content_from_uploadpdf(file: UploadFile):
    """
    Extract text content from an uploaded PDF file.
    Works directly with FastAPI's UploadFile.
    """
    text = ""
    title = file.filename
    print(f"Summarizing the {title}...........")

    try:
        # Read file bytes
        file_bytes = await file.read()

        # Use pdfplumber to read from memory
        from io import BytesIO
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

        return text.strip(), title

    except Exception as e:
        print(f"Error extracting PDF content: {str(e)}")
        return "", title


from pypdf import PdfReader
async def extract_content_from_url(url):
    # url = "https://www.dropbox.com/scl/fi/i4js5sapbbihzkbejonzy/provider-registration-policy.pdf?rlkey=2egqmz4na3g5v44w3976lpgo2&st=vicm51sf&dl=1"
    from io import BytesIO
    import requests
    data = requests.get(url)
    pdf_file = BytesIO(data.content)
    # Read PDF
    reader = PdfReader(pdf_file)

    # Extract all text
    data = ""
    for page in reader.pages:
        data += page.extract_text() + "\n"

    # Title from URL or PDF metadata
    title = reader.metadata.title if reader.metadata and reader.metadata.title else url.split("/")[-1].split("?")[0]

    # print("Title:", title)
    # print("Data (first 500 chars):", data[:500])
    return data, title