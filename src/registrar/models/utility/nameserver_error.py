from enum import IntEnum


class NameserverErrorCodes(IntEnum):
    """Used in the NameserverError class for
    error mapping.
    Overview of nameserver error codes:
        - 
    """

    MISSING_IP = 1
    GLUE_RECORD_NOT_ALLOWED = 2
    INVALID_IP = 3
    TOO_MANY_HOSTS=4



class NameserverError(Exception):
    """
    Overview of contact error codes:
      
    """

    # For linter

    _error_mapping = {
        NameserverErrorCodes.MISSING_IP: "Nameserver {} needs to have an "
                "IP address because it is a subdomain",
        NameserverErrorCodes.GLUE_RECORD_NOT_ALLOWED: "Nameserver {} cannot be linked "
                "because it is not a subdomain",
        NameserverErrorCodes.INVALID_IP:  "Nameserver {} has an invalid IP address: {}",
         NameserverErrorCodes.TOO_MANY_HOSTS:  "Too many hosts provided, you may not have more than 13 nameservers.",

    }

    def __init__(self, *args, code=None,nameserver=None,ip=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.code = code
        if self.code in self._error_mapping:
            self.message = self._error_mapping.get(self.code)
            if nameserver is not None and ip is not None:
                self.message=self.message.format(str(nameserver),str(ip))
            elif nameserver is not None:
                self.message=self.message.format(str(nameserver))
            elif ip is not None:
                self.message=self.message.format(str(ip))

    def __str__(self):
        return f"{self.message}"