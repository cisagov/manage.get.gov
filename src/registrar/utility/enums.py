"""Used for holding various enums"""

from enum import Enum


class ValidationErrorReturnType(Enum):
    """Determines the return value of the validate_and_handle_errors class"""
    JSON_RESPONSE = "JSON_RESPONSE"
    FORM_VALIDATION_ERROR = "FORM_VALIDATION_ERROR"


class LogCode(Enum):
    """Stores the desired log severity

    Overview of error codes:
    - 1 ERROR
    - 2 WARNING
    - 3 INFO
    - 4 DEBUG
    - 5 DEFAULT
    """

    ERROR = 1
    WARNING = 2
    INFO = 3
    DEBUG = 4
    DEFAULT = 5