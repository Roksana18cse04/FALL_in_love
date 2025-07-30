from datetime import datetime, timezone
from app.services.weaviate_client import client
from app.services.extract_content import extract_content_from_pdf
from app.services.upload_cloudinary import upload_pdf_to_cloudinary

class_name = "PolicyDocuments" 

def insert_to_weaviate(pdf_path, category="aged care"):
    
    try:
        # for source: upload file to cloudinary
        cloud_url = upload_pdf_to_cloudinary(pdf_path)

        # Extract content from PDF
        data, title = extract_content_from_pdf(pdf_path)
        # call summary generation function
        summary = data[:50] 

        # Ensure the client is connected
        if not client.is_connected():
            client.connect()

        data_object = {
            "title": title,
            "summary": summary,
            "category": category,
            "data": data,
            "source": cloud_url,
            "created_at": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
            "last_updated": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        }

        client.collections.get(class_name).data.insert(data_object)
        print(f"Data inserted into class '{class_name}' successfully.")
        
        
    except Exception as e:
        print(f"An error occurred while inserting data: {e}")

    client.close()  # Ensure the client connection is closed after the operation

from app.config import BASE_DIR

if __name__ == "__main__":
    pdf_path = f"{BASE_DIR}\provider-registration-policy.pdf"  # Replace with your PDF file path
    print(f"Inserting data from {pdf_path} into Weaviate...")

    insert_to_weaviate(pdf_path)
    print("Data insertion script executed.")