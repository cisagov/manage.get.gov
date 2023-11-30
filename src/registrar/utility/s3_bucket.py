"""Utilities for accessing an AWS S3 bucket"""

from enum import IntEnum
import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.template.loader import get_template

class S3ClientErrorCodes(IntEnum):
    """Used for S3ClientError
    Error code overview:
        - 1 ACCESS_S3_CLIENT_ERROR
        - 2 UPLOAD_FILE_ERROR
        - 3 FILE_NOT_FOUND_ERROR
        - 4 GET_FILE_ERROR
    """

    ACCESS_S3_CLIENT_ERROR = 1
    UPLOAD_FILE_ERROR = 2
    FILE_NOT_FOUND_ERROR = 3
    GET_FILE_ERROR = 4

class S3ClientError(RuntimeError):
    """Local error for handling all failures with boto3.client"""
    _error_mapping = {
        S3ClientErrorCodes.ACCESS_S3_CLIENT_ERROR: "Failed to establish a connection with the storage service.",
        S3ClientErrorCodes.UPLOAD_FILE_ERROR: "File upload to the storage service failed.",
        S3ClientErrorCodes.FILE_NOT_FOUND_ERROR: "Requested file not found in the storage service.",
        S3ClientErrorCodes.GET_FILE_ERROR: (
            "Retrieval of the requested file from " 
            "the storage service failed due to an unspecified error."
        ),
    }

    def __init__(self, *args, code=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.code = code
        if self.code in self._error_mapping:
            self.message = self._error_mapping.get(self.code)

    def __str__(self):
        return f"{self.message}"


class S3ClientHelper:
    """Helper class that simplifies S3 intialization"""
    def __init__(self):
        try:
            self.boto_client = boto3.client(
                "s3",
                region_name=settings.AWS_S3_REGION,
                aws_access_key_id=settings.AWS_S3_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_S3_SECRET_ACCESS_KEY,
                config=settings.BOTO_CONFIG,
            )
        except Exception as exc:
            raise S3ClientError(code=S3ClientErrorCodes.ACCESS_S3_CLIENT_ERROR) from exc

    def get_bucket_name(self):
        """Gets the name of our S3 Bucket"""
        return settings.AWS_S3_BUCKET_NAME

    def upload_file(self, file_path, file_name):
        """Uploads a file to our S3 instance"""
        try:
            response = self.boto_client.upload_file(file_path, self.get_bucket_name(), file_name)
        except Exception as exc:
            raise S3ClientError(code=S3ClientErrorCodes.UPLOAD_FILE_ERROR) from exc
        return response

    def get_file(self, file_name, decode_to_utf=False):
        """Gets a file to our S3 instance and returns the file content"""
        try:
            response = self.boto_client.get_object(Bucket=self.get_bucket_name(), Key=file_name)
        except ClientError as exc:
            if exc.response['Error']['Code'] == 'NoSuchKey':
                raise S3ClientError(code=S3ClientErrorCodes.FILE_NOT_FOUND_ERROR) from exc
            else:
                raise S3ClientError(code=S3ClientErrorCodes.GET_FILE_ERROR) from exc
        except Exception as exc:
            raise S3ClientError(code=S3ClientErrorCodes.GET_FILE_ERROR) from exc

        file_content = response["Body"].read()
        if decode_to_utf:
            return file_content.decode("utf-8")
        else:
            return file_content
