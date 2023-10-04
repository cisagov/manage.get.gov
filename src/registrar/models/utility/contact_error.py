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
    ...
