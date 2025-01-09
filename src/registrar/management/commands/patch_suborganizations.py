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
        # The key gets deleted, the value gets kept.
        additional_records_to_delete = {
            normalize_string("Assistant Secretary for Preparedness and Response Office of the Secretary"): {
                "keep": Suborganization.objects.none()
            },
            normalize_string("US Geological Survey"): {"keep": Suborganization.objects.none()},
            normalize_string("USDA/OC"): {"keep": Suborganization.objects.none()},
        }

        # First: Group all suborganization names by their "normalized" names (finding duplicates)
        name_groups = {}
        for suborg in Suborganization.objects.all():
            normalized_name = normalize_string(suborg.name)
            if normalized_name not in name_groups:
                name_groups[normalized_name] = []
            name_groups[normalized_name].append(suborg)

        # Second: find the record we should keep, and the duplicate records we should delete
        records_to_prune = {}
        for normalized_name, duplicate_suborgs in name_groups.items():
            if normalized_name in additional_records_to_delete:
                record = additional_records_to_delete.get(normalized_name)
                records_to_prune[normalized_name] = {"keep": record.get("keep"), "delete": duplicate_suborgs}
                continue

            if len(duplicate_suborgs) > 1:
                # Pick the best record to keep.
                # The fewest spaces and most capitals (at the beginning of each word) wins.
                best_record = duplicate_suborgs[0]
                for suborg in duplicate_suborgs:
                    has_fewer_spaces = suborg.name.count(" ") < best_record.name.count(" ")
                    has_more_capitals = count_capitals(suborg.name, leading_only=True) > count_capitals(
                        best_record.name, leading_only=True
                    )
                    if has_fewer_spaces or has_more_capitals:
                        best_record = suborg

                records_to_prune[normalized_name] = {
                    "keep": best_record,
                    "delete": [s for s in duplicate_suborgs if s != best_record],
                }

        if len(records_to_prune) == 0:
            TerminalHelper.colorful_logger(logger.error, TerminalColors.FAIL, "No suborganizations to delete.")
            return

        # Third: Show a preview of the changes
        total_records_to_remove = 0
        preview = "The following records will be removed:\n"
        for data in records_to_prune.values():
            keep = data.get("keep")
            if keep:
                preview += f"\nKeeping: '{keep.name}' (id: {keep.id})"

            for duplicate in data.get("delete"):
                preview += f"\nRemoving: '{duplicate.name}' (id: {duplicate.id})"
                total_records_to_remove += 1
            preview += "\n"

        # Fourth: Get user confirmation and execute deletions
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
                    # Update domain requests
                    DomainRequest.objects.filter(sub_organization_id__in=suborgs_to_remove).update(
                        sub_organization=best_record
                    )

                    # Update domain information
                    DomainInformation.objects.filter(sub_organization_id__in=suborgs_to_remove).update(
                        sub_organization=best_record
                    )

                    all_suborgs_to_remove.update(suborgs_to_remove)
                delete_count, _ = Suborganization.objects.filter(id__in=all_suborgs_to_remove).delete()
                TerminalHelper.colorful_logger(
                    logger.info, TerminalColors.MAGENTA, f"Successfully deleted {delete_count} suborganizations."
                )
            except Exception as e:
                TerminalHelper.colorful_logger(
                    logger.error, TerminalColors.FAIL, f"Failed to delete suborganizations: {str(e)}"
                )
