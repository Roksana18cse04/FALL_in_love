"""
AWS S3 Document Management Utility

This module provides functions for uploading and deleting documents 
from AWS S3 buckets with proper error handling and logging.
"""

import os
import logging
from typing import Optional
from pathlib import Path
from fastapi import UploadFile

import boto3
from botocore.exceptions import (
    NoCredentialsError,
    ClientError,
    BotoCoreError
)
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class S3Manager:
    """Manager class for AWS S3 operations."""
    
    def __init__(
        self,
        bucket_name: str = "policy-nest-bucket",
        region: str = "ap-southeast-2"
    ):

        self.bucket_name = bucket_name
        self.region = region
        self.s3_client = self._initialize_s3_client()
    
    def _initialize_s3_client(self) -> boto3.client:
        """
        Initialize and return S3 client with credentials from environment.
        
        Returns:
            Configured boto3 S3 client
            
        Raises:
            ValueError: If AWS credentials are not found
        """
        aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        
        if not aws_access_key or not aws_secret_key:
            raise ValueError(
                "AWS credentials not found. Please set AWS_ACCESS_KEY_ID "
                "and AWS_SECRET_ACCESS_KEY in your environment variables."
            )
        
        return boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=self.region
        )
    
    def upload_document(self, file: UploadFile, category: str, type: str):
        """Upload file and return VersionId"""
        try: 
            filename = file.filename
            object_key = f'AI/{type}/{category}/{filename}'
            response = self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=file.file  # UploadFile.file is file-like
            )
            version_id = response.get('VersionId')
            print(f"Uploaded {object_key} | VersionId: {version_id}")
            return {
                "object_key": object_key,
                "version_id": version_id
            }
        
        except Exception as e:
            print(f"Failed to upload file with version: {e}")
            return False
        
    
    def delete_document(self, version_id: str, object_key) -> bool:
        """
        Delete a specific version of an S3 object.
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=object_key,
                VersionId=version_id
            )
            print(f"Deleted version {version_id} of {object_key}")
            return True
        except Exception as e:
            print(f"Failed to delete version: {e}")
            return False
    
    def list_versions(self, object_key: str):
        """List all versions of a specific object (if versioning is enabled)."""
        try:
            versions = self.s3_client.list_object_versions(
                Bucket=self.bucket_name,
                Prefix=object_key
            )
            
            version_list = []
            for v in versions.get("Versions", []):
                logger.info(f"VersionId: {v['VersionId']} | LastModified: {v['LastModified']}")
                version_list.append({
                    "VersionId": v["VersionId"],
                    "LastModified": str(v["LastModified"]),
                    "IsLatest": v["IsLatest"]
                })
            return version_list
        except Exception as e:
            logger.error(f"Error listing versions: {e}")
            return []
        
    def download_document(self, object_key, download_path='temp_document.pdf'):
        try:
            self.s3_client.download_file(self.bucket_name, object_key, download_path)
            print(f"Downloaded successfully: {download_path}")
            return download_path  # explicitly return
        except Exception as e:
            print(f"Download failed: {e}")
            return None


def main():
    """Example usage of S3Manager."""
    try:
        # Initialize manager
        s3_manager = S3Manager()
        
        # Upload a document
        file_path = 'provider-registration-policy.pdf'
        category = 'privacy_confidentiality_information_governance'
        type = 'policy'
        
        # upload_response = s3_manager.upload_document(file_path, category, type)
        
        # if upload_response:
        #     print("upload response-------------", upload_response)
        # else:
        #     print("Upload failed. Check logs for details.")
        
        # Example: Delete a document
        version_id = 'OmHVItil.Jufl1j521INGOKUr1FClzco'
        success = s3_manager.delete_document(version_id, file_path, category, type)

        ######## all version find
        # object_key = f'AI/{type}/{category}/{file_path}'
        # list = s3_manager.list_versions(object_key)
        # print(f"all version list for {object_key}: {list}")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")



if __name__ == '__main__':
    main()