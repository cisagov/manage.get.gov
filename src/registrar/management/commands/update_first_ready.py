import logging
from django.core.management import BaseCommand
from registrar.management.commands.utility.terminal_helper import PopulateScriptTemplate, TerminalColors
from registrar.models import Domain, TransitionDomain

logger = logging.getLogger(__name__)


class Command(BaseCommand, PopulateScriptTemplate):
    help = "Loops through each domain object and populates the last_status_update and first_submitted_date"

    def handle(self, **kwargs):
        """Loops through each valid Domain object and updates it's first_ready value if it is out of sync"""
        filter_conditions = {"state__in": [Domain.State.READY, Domain.State.ON_HOLD, Domain.State.DELETED]}
        self.mass_update_records(Domain, filter_conditions, ["first_ready"], verbose=True)

    def update_record(self, record: Domain):
        """Defines how we update the first_ready field"""
        # update the first_ready value based on the creation date.
        record.first_ready = record.created_at.date()

        logger.info(
            f"{TerminalColors.OKCYAN}Updating {record} => first_ready: " f"{record.first_ready}{TerminalColors.ENDC}"
        )

    # check if a transition domain object for this domain name exists,
    # or if so whether its first_ready value matches its created_at date
    def custom_filter(self, records):
        to_include_pks = []
        for record in records:
            if (
                TransitionDomain.objects.filter(domain_name=record.name).exists()
                and record.first_ready != record.created_at.date()
            ):  # noqa
                to_include_pks.append(record.pk)

        return records.filter(pk__in=to_include_pks)
