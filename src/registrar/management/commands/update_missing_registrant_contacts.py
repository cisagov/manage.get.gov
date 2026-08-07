"""Update missing registrant contact info

This command is intended to fill in the missing registrant contact info and sync that data with the registry

- In dry-run mode (default), only logs what would be changed
- With --no-dry-run, sends registry updates via Domain.addRegistrant()
"""

import logging
import argparse
from django.core.management import BaseCommand
from registrar.models import PublicContact, Domain

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Updates registrant contact info for any domains which are missing the info"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            "--dry_run",
            action=argparse.BooleanOptionalAction,
            default=True,
            help=(
                "When enabled (which is the default), does not call the registry; only reports what would be updated. "
                "Disable with --no-dry-run to perform updates."
                "For dry run: ./manage.py update_missing_registrant_contacts"
                "For not dry run: ./manage.py update_missing_registrant_contacts --no-dry-run"
            ),
        )
        parser.add_argument(
            "--target-domain",
            "--target_domain",
            required=False,
            help="Only update contacts for a given domain name (case insensitive).",
        )

    def handle(self, *args, **options):
        logger.debug("Running missing registrants update script")
        dry_run = bool(options.get("dry_run", True))
        target_domain = options.get("target_domain", None)

        # Get domains
        if target_domain:
            domains_list = Domain.objects.filter(
                name=target_domain, state__in=[Domain.State.READY, Domain.State.DNS_NEEDED]
            )
        else:
            domains_list = Domain.objects.filter(state__in=[Domain.State.READY, Domain.State.DNS_NEEDED])

        add_count = 0
        fail_count = 0
        # Loop thru the domains
        for domain in domains_list:
            # If this is a dry run, just output the domain for tracking purposes
            if dry_run:
                add_count += 1
                logger.info(f"Dry run enabled...skipping adding registrant for {domain.name}")
            # Add the registrant
            else:
                logger.info(f"Creating Registrant Public Contact for {domain.name}")
                try:
                    registrant = PublicContact.objects.filter(
                        domain=domain, contact_type=PublicContact.ContactTypeChoices.REGISTRANT
                    ).first()
                    if registrant is None:
                        registry_id = domain.addRegistrant()
                        registrant = PublicContact.objects.filter(
                            domain=domain,
                            registry_id=registry_id,
                            contact_type=PublicContact.ContactTypeChoices.REGISTRANT,
                        ).first()
                    # This is needed because currently, the Admin contact is listed as the registrant in CloudFlare
                    # and the addRegistrant method requires the Registrant contact to be blank in Cloudflare to
                    # update it. Due to this, we use _add_registrant_to_existing_domain to force update it.
                    logger.info(
                        f"Updating registry Registrant Public Contact {registrant.registry_id} for {domain.name}"
                    )
                    try:
                        # This is a one off script, makes more sense to use the internal method than create
                        # a new public access method which we need to maintain.
                        domain._add_registrant_to_existing_domain(registrant)
                        add_count += 1
                    except Exception as e:
                        logger.error(f"Error updating domain in registry {domain.name}: {e}")
                        fail_count += 1
                except Exception as e:
                    logger.error(f"Error adding domain registrant {domain.name}: {e}")
                    fail_count += 1
        logger.info("DRYRUN SUMMARY:" if dry_run else "SUMMARY:")
        logger.info(f"Added {add_count} Registrant Contacts")
        logger.info(f"Failed to add {fail_count} Registrant Contacts")
