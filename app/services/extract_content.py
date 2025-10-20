import pdfplumber
import os
from fastapi import UploadFile
import re

def clean_ocr_noise(text):
    # Remove broken characters from OCR output
    text = re.sub(r'[|_—–•·“”‘’]', '', text)

    # Fix hyphenated words broken at line endings
    text = re.sub(r'(\w+)-\s+(\w+)', r'\1\2', text)

    # Remove dotted leaders like ". . . . ." or ". . ."
    text = re.sub(r'(\.\s*){2,}', ' ', text)

    # Normalize multiple dots or commas (e.g., "....." → ".")
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r',,', ',', text)

    # Optional: remove trailing numbers from headings like "13"
    text = re.sub(r'\s+\d+\s*$', '', text, flags=re.MULTILINE)

    return text


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
        clean_text = clean_ocr_noise(text)
        return clean_text, title

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

        clean_text = clean_ocr_noise(text)
        return clean_text, title

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