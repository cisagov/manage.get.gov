from dataclasses import dataclass


@dataclass
class TransitionDomainArguments:
    """Stores arguments for load_transition_domain"""
    # Settings #
    directory: str
    seperator: str
    limit_parse: int
    
    # Filenames #
    ## Adhocs ##
    agency_adhoc_filename: str
    domain_adhoc_filename: str
    organization_adhoc_filename: str

    ## Data files ##
    domain_additional_filename: str
    domain_contacts_filename: str
    domain_statuses_filename: str

    # Flags #
    debug: bool
    reset_table: bool
    load_extra: bool