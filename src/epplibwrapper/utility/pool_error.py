from enum import IntEnum


class PoolErrorCodes(IntEnum):
    """Used in the PoolError class for
    error mapping.

    Overview of contact error codes:
        - 2000 KILL_ALL_FAILED
        - 2001 NEW_CONNECTION_FAILED
        - 2002 KEEP_ALIVE_FAILED
        - 2003 INVALID_CLIENT_TYPE
    """

    KILL_ALL_FAILED = 2000
    NEW_CONNECTION_FAILED = 2001
    KEEP_ALIVE_FAILED = 2002
    INVALID_CLIENT_TYPE = 2003


class PoolError(Exception):
    """
    Overview of contact error codes:
        - 2000 KILL_ALL_FAILED
        - 2001 NEW_CONNECTION_FAILED
        - 2002 KEEP_ALIVE_FAILED
        - 2003 INVALID_CLIENT_TYPE
    """

    # For linter
    kill_failed = "Could not kill all connections."
    conn_failed = "Failed to execute due to a registry error."
    alive_failed = "Failed to keep the connection alive."
    invalid_client = "Invalid client type."
    _error_mapping = {
        PoolErrorCodes.KILL_ALL_FAILED: kill_failed,
        PoolErrorCodes.NEW_CONNECTION_FAILED: conn_failed,
        PoolErrorCodes.KEEP_ALIVE_FAILED: alive_failed,
        PoolErrorCodes.INVALID_CLIENT_TYPE: invalid_client
    }

    def __init__(self, *args, code=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.code = code
        if self.code in self._error_mapping:
            self.message = self._error_mapping.get(self.code)

    def __str__(self):
        return f"{self.message}"
