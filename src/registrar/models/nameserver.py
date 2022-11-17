from .host import Host

class Nameserver(Host):
    """
    A nameserver is a host which has been delegated to respond to DNS queries.

    The registry is the source of truth for this data.

    This model exists ONLY to allow a new registrant to draft DNS entries
    before their application is approved.
    """
    pass