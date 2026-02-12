import logging
from django.core.management import BaseCommand
from registrar.models import Suborganization, DomainRequest, DomainInformation
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper
from registrar.models.utility.generic_helper import count_capitals, normalize_string

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Clean up duplicate suborganizations that differ only by spaces and capitalization"

    def handle(self, **kwargs):
        """Process manual deletions and find/remove duplicates. Shows preview
        and updates DomainInformation / DomainRequest sub_organization references before deletion."""

        # First: get a preset list of records we want to delete.
        # For extra_records_to_prune: the key gets deleted, the value gets kept.
        extra_records_to_prune = {
            normalize_string("Assistant Secretary for Preparedness and Response Office of the Secretary"): {
                "replace_with": "Assistant Secretary for Preparedness and Response, Office of the Secretary"
            },
            normalize_string("US Geological Survey"): {"replace_with": "U.S. Geological Survey"},
            normalize_string("USDA/OC"): {"replace_with": "USDA, Office of Communications"},
            normalize_string("GSA, IC, OGP WebPortfolio"): {"replace_with": "GSA, IC, OGP Web Portfolio"},
            normalize_string("USDA/ARS/NAL"): {"replace_with": "USDA, ARS, NAL"},
        }

        # Second: loop through every Suborganization and return a dict of what to keep, and what to delete
        # for each duplicate or "incorrect" record. We do this by pruning records with extra spaces or bad caps
        # Note that "extra_records_to_prune" is just a manual mapping.
        records_to_prune = self.get_records_to_prune(extra_records_to_prune)
        if len(records_to_prune) == 0:
            TerminalHelper.colorful_logger(logger.error, TerminalColors.FAIL, "No suborganizations to delete.")
            return

        # Third: Build a preview of the changes
        total_records_to_remove = 0
        preview_lines = ["The following records will be removed:"]
        for data in records_to_prune.values():
            keep = data.get("keep")
            delete = data.get("delete")
            if keep:
                preview_lines.append(f"Keeping: '{keep.name}' (id: {keep.id})")

            for duplicate in delete:
                preview_lines.append(f"Removing: '{duplicate.name}' (id: {duplicate.id})")
                total_records_to_remove += 1
            preview_lines.append("")
        preview = "\n".join(preview_lines)

        # Fourth: Get user confirmation and delete
        if TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            prompt_message=preview,
            prompt_title=f"Remove {total_records_to_remove} suborganizations?",
            verify_message="*** WARNING: This will replace the record on DomainInformation and DomainRequest! ***",
        ):
            try:
                # Update all references to point to the right suborg before deletion
                all_suborgs_to_remove = set()
                for record in records_to_prune.values():
                    best_record = record["keep"]
                    suborgs_to_remove = {dupe.id for dupe in record["delete"]}
                    DomainRequest.objects.filter(sub_organization_id__in=suborgs_to_remove).update(
                        sub_organization=best_record
                    )
                    DomainInformation.objects.filter(sub_organization_id__in=suborgs_to_remove).update(
                        sub_organization=best_record
                    )
                    all_suborgs_to_remove.update(suborgs_to_remove)
                # Delete the suborgs
                delete_count, _ = Suborganization.objects.filter(id__in=all_suborgs_to_remove).delete()
                TerminalHelper.colorful_logger(
                    logger.info, TerminalColors.MAGENTA, f"Successfully deleted {delete_count} suborganizations."
                )
            except Exception as e:
                TerminalHelper.colorful_logger(
                    logger.error, TerminalColors.FAIL, f"Failed to delete suborganizations: {str(e)}"
                )

    def get_records_to_prune(self, extra_records_to_prune):
        """Maps all suborgs into a dictionary with a record to keep, and an array of records to delete."""
        # First: Group all suborganization names by their "normalized" names (finding duplicates).
        # Returns a dict that looks like this:
        # {
        #   "amtrak": [<Suborganization: AMTRAK>, <Suborganization: aMtRaK>, <Suborganization: AMTRAK  >],
        #   "usda/oc": [<Suborganization: USDA/OC>],
        #   ...etc
        # }
        #
        name_groups = {}
        for suborg in Suborganization.objects.all():
            normalized_name = normalize_string(suborg.name)
            name_groups.setdefault(normalized_name, []).append(suborg)

        # Second: find the record we should keep, and the records we should delete
        # Returns a dict that looks like this:
        # {
        #  "amtrak": {
        #       "keep": <Suborganization: AMTRAK>
        #       "delete": [<Suborganization: aMtRaK>, <Suborganization: AMTRAK  >]
        #   },
        #   "usda/oc": {
        #       "keep": <Suborganization: USDA, Office of Communications>,
        #       "delete": [<Suborganization: USDA/OC>]
        #   },
        #   ...etc
        # }
        records_to_prune = {}
        for normalized_name, duplicate_suborgs in name_groups.items():
            # Delete data from our preset list
            if normalized_name in extra_records_to_prune:
                # The 'keep' field expects a Suborganization but we just pass in a string, so this is just a workaround.
                # This assumes that there is only one item in the name_group array (see usda/oc example).
                # But this should be fine, given our data.
                hardcoded_record_name = extra_records_to_prune[normalized_name]["replace_with"]
                name_group = name_groups.get(normalize_string(hardcoded_record_name))
                keep = name_group[0] if name_group else None
                records_to_prune[normalized_name] = {"keep": keep, "delete": duplicate_suborgs}
            # Delete duplicates (extra spaces or casing differences)
            elif len(duplicate_suborgs) > 1:
                # Pick the best record (fewest spaces, most leading capitals)
                best_record = max(
                    duplicate_suborgs,
                    key=lambda suborg: (-suborg.name.count(" "), count_capitals(suborg.name, leading_only=True)),
                )
                records_to_prune[normalized_name] = {
                    "keep": best_record,
                    "delete": [s for s in duplicate_suborgs if s != best_record],
                }
        return records_to_prune
