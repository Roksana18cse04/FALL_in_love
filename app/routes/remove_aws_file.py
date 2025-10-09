from fastapi import APIRouter, HTTPException
from app.services.s3_manager import S3Manager
from fastapi.responses import JSONResponse

router = APIRouter()

s3_manager = S3Manager()

@router.post("/delete-cloud-file")
async def delete_cloud_file_endpoint(version_id, object_key):
    # Implement your summary logic here
    try:

        # upload to cloud storage
        response = s3_manager.delete_document(version_id, object_key)
        if response:
            return JSONResponse(status_code=200, content={
                "status": "Success",
                "message": "File Removed Successfully."
            })
        else:
            print('File Removed Failed')
            return JSONResponse(status_code=500, content={
                "status": "error",
                "message": "File upload failed."
            })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error for Deleting AWS files: {str(e)}")