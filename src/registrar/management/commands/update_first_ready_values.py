import logging
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import PopulateScriptTemplate, TerminalColors
from registrar.models import Domain, TransitionDomain

logger = logging.getLogger(__name__)

class Command(BaseCommand, PopulateScriptTemplate):
    help = "Loops through eachdomain object and populates the last_status_update and first_submitted_date"

    def handle(self, **kwargs):
        """Loops through each valid Domain object and updates it's first_ready value if they are out of sync"""
        filter_conditions="state__in=[Domain.State.READY, Domain.State.ON_HOLD, Domain.State.DELETED]"
        self.mass_update_records(Domain, filter_conditions, ["first_ready"])

    def update_record(self, record: Domain):
        """Defines how we update the first_read field"""
        # if these are out of sync, update the 
        if self.is_transition_domain(record) and record.first_ready != record.created_at:
            record.first_ready = record.created_at

        logger.info(
            f"{TerminalColors.OKCYAN}Updating {record} => first_ready: " f"{record.first_ready}{TerminalColors.OKCYAN}"
        )
    
    # check if a transition domain object for this domain name exists
    def is_transition_domain(record: Domain):
        return TransitionDomain.objects.filter(domain_name=record.name).exists()