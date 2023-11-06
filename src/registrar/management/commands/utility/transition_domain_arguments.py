from dataclasses import dataclass, field
from typing import Optional

from registrar.management.commands.utility.epp_data_containers import EnumFilenames

@dataclass
class TransitionDomainArguments:
    """Stores arguments for load_transition_domain"""
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)

    # Settings #
    directory: Optional[str] = field(default="migrationdata", repr=True)
    sep: Optional[str] = field(default="|", repr=True)
    limitParse: Optional[int] = field(default=None, repr=True)

    # Filenames #
    ## Adhocs ##
    agency_adhoc_filename: Optional[str] = field(default=EnumFilenames.AGENCY_ADHOC.value[1], repr=True)
    domain_adhoc_filename: Optional[str] = field(default=EnumFilenames.DOMAIN_ADHOC.value[1], repr=True)
    organization_adhoc_filename: Optional[str] = field(default=EnumFilenames.ORGANIZATION_ADHOC.value[1], repr=True)
    authority_adhoc_filename: Optional[str] = field(default=EnumFilenames.AUTHORITY_ADHOC.value[1], repr=True)

    ## Data files ##
    domain_escrow_filename: Optional[str] = field(default=EnumFilenames.DOMAIN_ESCROW.value[1], repr=True)
    domain_additional_filename: Optional[str] = field(default=EnumFilenames.DOMAIN_ADDITIONAL.value[1], repr=True)
    domain_contacts_filename: Optional[str] = field(default=None, repr=True)
    domain_statuses_filename: Optional[str] = field(default=None, repr=True)

    # Flags #
    debug: Optional[bool] = field(default=False, repr=True)
    resetTable: Optional[bool] = field(default=False, repr=True)
    infer_filenames: Optional[bool] = field(default=False, repr=True)
