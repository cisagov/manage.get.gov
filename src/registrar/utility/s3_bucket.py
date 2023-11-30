"""Utilities for accessing an AWS S3 bucket"""

import boto3

from django.conf import settings
from django.template.loader import get_template


class S3ClientError(RuntimeError):
    """Local error for handling all failures with boto3.client"""
    pass


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
            raise S3ClientError("Could not access the S3 client") from exc

    def get_bucket_name(self):
        """Gets the name of our S3 Bucket"""
        return settings.AWS_S3_BUCKET_NAME

    def upload_file(self, file_path, file_name):
        """Uploads a file to our S3 instance"""
        try:
            response = self.boto_client.upload_file(file_path, self.get_bucket_name(), file_name)
        except Exception as exc:
            raise S3ClientError("Couldn't upload file") from exc
        return response

    def get_file(self, file_name, decode_to_utf=False):
        """Gets a file to our S3 instance and returns the file content"""
        try:
            response = self.boto_client.get_object(Bucket=self.get_bucket_name(), Key=file_name)
        except self.boto_client.exceptions.NoSuchKey as exc:
            raise S3ClientError("File was not found") from exc
        except Exception as exc:
            raise S3ClientError("Couldn't get file, an unspecified error occured") from exc

        file_content = response["Body"].read()
        if decode_to_utf:
            return file_content.decode("utf-8")
        else:
            return file_content
