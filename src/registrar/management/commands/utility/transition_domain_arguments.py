class TransitionDomainArguments:
    """Stores arguments for load_transition_domain"""

    def __init__(self, **options):
        # Settings #
        self.directory = options.get("directory")
        self.sep = options.get("sep")
        self.limitParse = options.get("limitParse")

        # Filenames #
        ## Adhocs ##
        self.agency_adhoc_filename = options.get("agency_adhoc_filename")
        self.domain_adhoc_filename = options.get("domain_adhoc_filename")
        self.organization_adhoc_filename = options.get("organization_adhoc_filename")

        ## Data files ##
        self.domain_additional_filename = options.get("domain_additional_filename")
        self.domain_contacts_filename = options.get("domain_contacts_filename")
        self.domain_statuses_filename = options.get("domain_statuses_filename")

        # Flags #
        self.debug = options.get("debug")
        self.resetTable = options.get("resetTable")

    def args_extra_transition_domain(self):
        return {
            "agency_adhoc_filename": self.agency_adhoc_filename,
            "domain_adhoc_filename": self.domain_adhoc_filename,
            "organization_adhoc_filename": self.organization_adhoc_filename,
            "domain_additional_filename": self.domain_additional_filename,
            "directory": self.directory,
            "sep": self.sep,
        }
