from enum import IntEnum


class ContactErrorCodes(IntEnum):
    """Used in the ContactError class for
    error mapping.

    Overview of contact error codes:
        - 2000 CONTACT_TYPE_NONE
        - 2001 CONTACT_ID_NONE
        - 2002 CONTACT_ID_INVALID_LENGTH
        - 2003 CONTACT_INVALID_TYPE
    """

    CONTACT_TYPE_NONE = 2000
    CONTACT_ID_NONE = 2001
    CONTACT_ID_INVALID_LENGTH = 2002
    CONTACT_INVALID_TYPE = 2003
    CONTACT_NOT_FOUND = 2004


class ContactError(Exception):
    """
    Overview of contact error codes:
        - 2000 CONTACT_TYPE_NONE
        - 2001 CONTACT_ID_NONE
        - 2002 CONTACT_ID_INVALID_LENGTH
        - 2003 CONTACT_INVALID_TYPE
        - 2004 CONTACT_NOT_FOUND
    """

    # For linter
    _contact_id_error = "contact_id has an invalid length. Cannot exceed 16 characters."
    _contact_invalid_error = "Contact must be of type InfoContactResultData"
    _contact_not_found_error = "No contact was found in cache or the registry"
    _error_mapping = {
        ContactErrorCodes.CONTACT_TYPE_NONE: "contact_type is None",
        ContactErrorCodes.CONTACT_ID_NONE: "contact_id is None",
        ContactErrorCodes.CONTACT_ID_INVALID_LENGTH: _contact_id_error,
        ContactErrorCodes.CONTACT_INVALID_TYPE: _contact_invalid_error,
        ContactErrorCodes.CONTACT_NOT_FOUND: _contact_not_found_error,
    }

    def __init__(self, *args, code=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.code = code
        if self.code in self._error_mapping:
            self.message = self._error_mapping.get(self.code)

    def __str__(self):
        return f"{self.message}"
