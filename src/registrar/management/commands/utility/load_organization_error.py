from enum import IntEnum


class LoadOrganizationErrorCodes(IntEnum):
    """Used when running the load_organization_data script
    Overview of error codes:
        - 1 TRANSITION_DOMAINS_NOT_FOUND
        - 2 UPDATE_DOMAIN_INFO_FAILED
        - 3 EMPTY_TRANSITION_DOMAIN_TABLE
    """

    TRANSITION_DOMAINS_NOT_FOUND = 1
    UPDATE_DOMAIN_INFO_FAILED = 2
    EMPTY_TRANSITION_DOMAIN_TABLE = 3
    DOMAIN_NAME_WAS_NONE = 4


class LoadOrganizationError(Exception):
    """
    Error class used in the load_organization_data script
    """

    _error_mapping = {
        LoadOrganizationErrorCodes.TRANSITION_DOMAINS_NOT_FOUND: (
            "Could not find all desired TransitionDomains. " "(Possible data corruption?)"
        ),
        LoadOrganizationErrorCodes.UPDATE_DOMAIN_INFO_FAILED: "Failed to update DomainInformation",
        LoadOrganizationErrorCodes.EMPTY_TRANSITION_DOMAIN_TABLE: "No TransitionDomains exist. Cannot update.",
        LoadOrganizationErrorCodes.DOMAIN_NAME_WAS_NONE: "DomainInformation was updated, but domain was None",
    }

    def __init__(self, *args, code=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.code = code
        if self.code in self._error_mapping:
            self.message = self._error_mapping.get(self.code)

    def __str__(self):
        return f"{self.message}"
