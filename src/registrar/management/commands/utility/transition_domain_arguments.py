from dataclasses import dataclass, field
from typing import Optional

from registrar.management.commands.utility.epp_data_containers import EnumFilenames


@dataclass
class TransitionDomainArguments:
    """Stores arguments for load_transition_domain, structurally a mix
    of a dataclass and a regular class, meaning we get a hardcoded
    representation of the values we want, while maintaining flexiblity
    and reducing boilerplate.

    All pre-defined fields are optional but will remain on the model definition.
    In this event, they are provided a default value if none is given.
    """

    # Maintains an internal kwargs list and sets values
    # that match the class definition.
    def __init__(self, **kwargs):
        self.pattern_map_params = kwargs.get("pattern_map_params", [])
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)

    # These all use field() to minimize typing and/or lambda.
    # Since this file is bound to expand, we can save time
    # by reducing the line count from 2-3 to just 1 line
    # each time we want to add a new filename or option.

    # This approach is also used in EppLib internally for similar reasons.

    # Settings #
    directory: Optional[str] = field(default="migrationdata", repr=True)
    sep: Optional[str] = field(default="|", repr=True)
    limitParse: Optional[int] = field(default=None, repr=True)

    # Filenames #
    # = Adhocs = #
    agency_adhoc_filename: Optional[str] = field(default=EnumFilenames.AGENCY_ADHOC.value[1], repr=True)
    domain_adhoc_filename: Optional[str] = field(default=EnumFilenames.DOMAIN_ADHOC.value[1], repr=True)
    organization_adhoc_filename: Optional[str] = field(default=EnumFilenames.ORGANIZATION_ADHOC.value[1], repr=True)
    authority_adhoc_filename: Optional[str] = field(default=EnumFilenames.AUTHORITY_ADHOC.value[1], repr=True)

    # = Data files = #
    domain_escrow_filename: Optional[str] = field(default=EnumFilenames.DOMAIN_ESCROW.value[1], repr=True)
    domain_additional_filename: Optional[str] = field(default=EnumFilenames.DOMAIN_ADDITIONAL.value[1], repr=True)
    domain_contacts_filename: Optional[str] = field(default=None, repr=True)
    domain_statuses_filename: Optional[str] = field(default=None, repr=True)
    contacts_filename: Optional[str] = field(default=None, repr=True)

    # Flags #
    debug: Optional[bool] = field(default=False, repr=True)
    resetTable: Optional[bool] = field(default=False, repr=True)
    infer_filenames: Optional[bool] = field(default=False, repr=True)
