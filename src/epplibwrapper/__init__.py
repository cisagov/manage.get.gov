import logging
from types import SimpleNamespace

try:
    from epplib import constants
except ImportError:
    # allow epplibwrapper to load without epplib, for testing and development
    pass

logger = logging.getLogger(__name__)

NAMESPACE = SimpleNamespace(
    EPP="urn:ietf:params:xml:ns:epp-1.0",
    SEC_DNS="urn:ietf:params:xml:ns:secDNS-1.1",
    XSI="http://www.w3.org/2001/XMLSchema-instance",
    FRED="noop",
    NIC_CONTACT="urn:ietf:params:xml:ns:contact-1.0",
    NIC_DOMAIN="urn:ietf:params:xml:ns:domain-1.0",
    NIC_ENUMVAL="noop",
    NIC_EXTRA_ADDR="noop",
    NIC_HOST="urn:ietf:params:xml:ns:host-1.0",
    NIC_KEYSET="noop",
    NIC_NSSET="noop",
)

SCHEMA_LOCATION = SimpleNamespace(
    XSI="urn:ietf:params:xml:ns:epp-1.0 epp-1.0.xsd",
    FRED="noop fred-1.5.0.xsd",
    SEC_DNS="urn:ietf:params:xml:ns:secDNS-1.1 secDNS-1.1.xsd",
    NIC_CONTACT="urn:ietf:params:xml:ns:contact-1.0 contact-1.0.xsd",
    NIC_DOMAIN="urn:ietf:params:xml:ns:domain-1.0 domain-1.0.xsd",
    NIC_ENUMVAL="noop enumval-1.2.0.xsd",
    NIC_EXTRA_ADDR="noop extra-addr-1.0.0.xsd",
    NIC_HOST="urn:ietf:params:xml:ns:host-1.0 host-1.0.xsd",
    NIC_KEYSET="noop keyset-1.3.2.xsd",
    NIC_NSSET="noop nsset-1.2.2.xsd",
)

try:
    constants.NAMESPACE = NAMESPACE
    constants.SCHEMA_LOCATION = SCHEMA_LOCATION
except NameError:
    pass

# Attn: these imports should NOT be at the top of the file
try:
    from .client import CLIENT, commands
    from .errors import RegistryError, ErrorCode
    from epplib.models import common, info
    from epplib.responses import extensions
    from epplib import responses
except ImportError:
    pass

__all__ = [
    "CLIENT",
    "commands",
    "common",
    "extensions",
    "responses",
    "info",
    "ErrorCode",
    "RegistryError",
]
