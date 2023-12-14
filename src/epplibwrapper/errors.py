from enum import IntEnum


class ErrorCode(IntEnum):
    """
    Overview of registry response codes from RFC 5730. See RFC 5730 for full text.
        - 0 System connection error
        - 1000 - 1500 Success
        - 2000 - 2308 Registrar did something silly
        - 2400 - 2500 Registry did something silly
        - 2501 - 2502 Something malicious or abusive may have occurred
    """

    TRANSPORT_ERROR = 0

    COMMAND_COMPLETED_SUCCESSFULLY = 1000
    COMMAND_COMPLETED_SUCCESSFULLY_ACTION_PENDING = 1001
    COMMAND_COMPLETED_SUCCESSFULLY_NO_MESSAGES = 1300
    COMMAND_COMPLETED_SUCCESSFULLY_ACK_TO_DEQUEUE = 1301
    COMMAND_COMPLETED_SUCCESSFULLY_ENDING_SESSION = 1500

    UNKNOWN_COMMAND = 2000
    COMMAND_SYNTAX_ERROR = 2001
    COMMAND_USE_ERROR = 2002
    REQUIRED_PARAMETER_MISSING = 2003
    PARAMETER_VALUE_RANGE_ERROR = 2004
    PARAMETER_VALUE_SYNTAX_ERROR = 2005
    UNIMPLEMENTED_PROTOCOL_VERSION = 2100
    UNIMPLEMENTED_COMMAND = 2101
    UNIMPLEMENTED_OPTION = 2102
    UNIMPLEMENTED_EXTENSION = 2103
    BILLING_FAILURE = 2104
    OBJECT_IS_NOT_ELIGIBLE_FOR_RENEWAL = 2105
    OBJECT_IS_NOT_ELIGIBLE_FOR_TRANSFER = 2106
    AUTHENTICATION_ERROR = 2200
    AUTHORIZATION_ERROR = 2201
    INVALID_AUTHORIZATION_INFORMATION = 2202
    OBJECT_PENDING_TRANSFER = 2300
    OBJECT_NOT_PENDING_TRANSFER = 2301
    OBJECT_EXISTS = 2302
    OBJECT_DOES_NOT_EXIST = 2303
    OBJECT_STATUS_PROHIBITS_OPERATION = 2304
    OBJECT_ASSOCIATION_PROHIBITS_OPERATION = 2305
    PARAMETER_VALUE_POLICY_ERROR = 2306
    UNIMPLEMENTED_OBJECT_SERVICE = 2307
    DATA_MANAGEMENT_POLICY_VIOLATION = 2308

    COMMAND_FAILED = 2400
    COMMAND_FAILED_SERVER_CLOSING_CONNECTION = 2500

    AUTHENTICATION_ERROR_SERVER_CLOSING_CONNECTION = 2501
    SESSION_LIMIT_EXCEEDED_SERVER_CLOSING_CONNECTION = 2502


class RegistryError(Exception):
    """
    Overview of registry response codes from RFC 5730. See RFC 5730 for full text.

        - 1000 - 1500 Success
        - 2000 - 2308 Registrar did something silly
        - 2400 - 2500 Registry did something silly
        - 2501 - 2502 Something malicious or abusive may have occurred
    """

    def __init__(self, *args, code=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.code = code

    def should_retry(self):
        return self.code == ErrorCode.COMMAND_FAILED

    def is_transport_error(self):
        return self.code == ErrorCode.TRANSPORT_ERROR

    # connection errors have error code of None and [Errno 99] in the err message
    def is_connection_error(self):
        return self.code is None

    def is_session_error(self):
        return self.code is not None and (self.code >= 2501 and self.code <= 2502)

    def is_server_error(self):
        return self.code is not None and (self.code >= 2400 and self.code <= 2500)

    def is_client_error(self):
        return self.code is not None and (self.code >= 2000 and self.code <= 2308)


class LoginError(RegistryError):
    pass
