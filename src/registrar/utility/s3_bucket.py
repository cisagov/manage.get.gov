"""Utilities for accessing an AWS S3 bucket"""

from enum import IntEnum
import boto3
from botocore.exceptions import ClientError
from django.conf import settings


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
    """
    Custom exception class for handling errors related to interactions with the S3 storage service via boto3.client.

    This class maps error codes to human-readable error messages. When an instance of S3ClientError is created,
    an error code can be passed in to set the error message for that instance.

    Attributes:
        _error_mapping: A dictionary mapping error codes to error messages.
        code: The error code for a specific instance of S3ClientError.
        message: The error message for a specific instance of S3ClientError, determined by the error code.
    """

    _error_mapping = {
        S3ClientErrorCodes.ACCESS_S3_CLIENT_ERROR: "Failed to establish a connection with the storage service.",
        S3ClientErrorCodes.UPLOAD_FILE_ERROR: "File upload to the storage service failed.",
        S3ClientErrorCodes.FILE_NOT_FOUND_ERROR: "Requested file not found in the storage service.",
        S3ClientErrorCodes.GET_FILE_ERROR: (
            "Retrieval of the requested file from " "the storage service failed due to an unspecified error."
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
    """
    A helper class for interacting with Amazon S3 via the boto3 client.

    This class simplifies the process of initializing the boto3 client,
    uploading files to S3, and retrieving files from S3.

    Attributes:
        boto_client: The boto3 client used to interact with S3.
    """

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
        """
        Retrieves the name of the S3 bucket.

        This method returns the name of the S3 bucket as defined in the application's settings.

        Returns:
            str: The name of the S3 bucket.
        """

        return settings.AWS_S3_BUCKET_NAME

    def upload_file(self, file_path, file_name):
        """
        Uploads a file to the S3 bucket.

        This method attempts to upload a file to the S3 bucket using the boto3 client.
        If an exception occurs during the upload process, it raises an S3ClientError with an UPLOAD_FILE_ERROR code.

        Args:
            file_path (str): The path of the file to upload.
            file_name (str): The name to give to the file in the S3 bucket.

        Returns:
            dict: The response from the boto3 client's upload_file method.

        Raises:
            S3ClientError: If the file cannot be uploaded to the S3 bucket.
        """

        try:
            response = self.boto_client.upload_file(file_path, self.get_bucket_name(), file_name)
        except Exception as exc:
            raise S3ClientError(code=S3ClientErrorCodes.UPLOAD_FILE_ERROR) from exc
        return response

    def get_file(self, file_name, decode_to_utf=False):
        """
        Retrieves a file from the S3 bucket and returns its content.

        This method attempts to retrieve a file from the S3 bucket using the boto3 client.
        If the file is not found, it raises an S3ClientError with a FILE_NOT_FOUND_ERROR code.
        For any other exceptions during the retrieval process, it raises an S3ClientError with a GET_FILE_ERROR code.

        Args:
            file_name (str): The name of the file to retrieve from the S3 bucket.
            decode_to_utf (bool, optional): If True, the file content is decoded from bytes to a UTF-8 string.
                Defaults to False.

        Returns:
            bytes or str: The content of the file. If decode_to_utf is True, this is a string. Otherwise, its bytes.

        Raises:
            S3ClientError: If the file cannot be retrieved from the S3 bucket.
        """

        try:
            response = self.boto_client.get_object(Bucket=self.get_bucket_name(), Key=file_name)
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "NoSuchKey":
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
