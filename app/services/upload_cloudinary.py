import cloudinary
import cloudinary.uploader

def upload_pdf_to_cloudinary(local_path, folder="policies"):
    response = cloudinary.uploader.upload(
        local_path,
        resource_type="raw",
        type="upload",
        folder=folder,
        use_filename=True,
        unique_filename=False
    )
    if "secure_url" not in response:
        raise Exception("Failed to upload PDF to Cloudinary")
    print(f"PDF uploaded to Cloudinary: {response['secure_url']}")
    return response["secure_url"]

