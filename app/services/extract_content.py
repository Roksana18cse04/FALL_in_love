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