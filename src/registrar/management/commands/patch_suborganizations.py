@ -0,0 +1,123 @@
import logging
from django.core.management import BaseCommand
from registrar.models import Suborganization, DomainRequest, DomainInformation
from registrar.management.commands.utility.terminal_helper import TerminalColors, TerminalHelper
from registrar.models.utility.generic_helper import normalize_string


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Clean up duplicate suborganizations that differ only by spaces and capitalization"

    def handle(self, **kwargs):
        manual_records = [
            "Assistant Secretary for Preparedness and Response Office of the Secretary",
            "US Geological Survey",
            "USDA/OC",
        ]
        duplicates = {}
        for record in Suborganization.objects.filter(name__in=manual_records):
            if record.name:
                norm_name = normalize_string(record.name)
                duplicates[norm_name] = {
                    "keep": None,
                    "delete": [record]
                }

        records_to_delete.update(self.handle_suborganization_duplicates())

        # Get confirmation and execute deletions
        if TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            prompt_message=preview,
            prompt_title="Clean up duplicate suborganizations?",
            verify_message="*** WARNING: This will delete suborganizations! ***"
        ):
            # Update all references to point to the right suborg before deletion
            for record in duplicates.values():
                best_record = record.get("keep")
                delete_ids = [dupe.id for dupe in record.get("delete")]
                
                # Update domain requests
                DomainRequest.objects.filter(
                    sub_organization_id__in=delete_ids
                ).update(sub_organization=best_record)
                
                # Update domain information
                DomainInformation.objects.filter(
                    sub_organization_id__in=delete_ids
                ).update(sub_organization=best_record)

            records_to_delete = set(
                dupe.id 
                for data in duplicates.values() 
                for dupe in data["delete"]
            )
            try:
                delete_count, _ = Suborganization.objects.filter(id__in=records_to_delete).delete()
                logger.info(f"{TerminalColors.OKGREEN}Successfully deleted {delete_count} suborganizations{TerminalColors.ENDC}")
            except Exception as e:
                logger.error(f"{TerminalColors.FAIL}Failed to clean up suborganizations: {str(e)}{TerminalColors.ENDC}")


    def handle_suborganization_duplicates(self, duplicates):
        # Find duplicates
        all_suborgs = Suborganization.objects.all()
        for suborg in all_suborgs:
            # Normalize name by removing extra spaces and converting to lowercase
            normalized_name = " ".join(suborg.name.split()).lower()
            
            # First occurrence of this name
            if normalized_name not in duplicates:
                duplicates[normalized_name] = {
                    "keep": suborg,
                    "delete": []
                }
                continue

            # Compare with our current best
            current_best = duplicates[normalized_name]["keep"]

            # Check if all other fields match.
            # If they don't, we should inspect this record manually.
            fields_to_compare = ["portfolio", "city", "state_territory"]
            fields_match = all(
                getattr(suborg, field) == getattr(current_best, field)
                for field in fields_to_compare
            )
            if not fields_match:
                logger.warning(
                    f"{TerminalColors.YELLOW}"
                    f"\nSkipping potential duplicate: {suborg.name} (id: {suborg.id})"
                    f"\nData mismatch with {current_best.name} (id: {current_best.id})"
                    f"{TerminalColors.ENDC}"
                )
                continue
            
            # Determine if new suborg is better than current best.
            # The fewest spaces and most capitals wins.
            new_has_fewer_spaces = suborg.name.count(" ") < current_best.name.count(" ")
            new_has_more_capitals = sum(1 for c in suborg.name if c.isupper()) > sum(1 for c in current_best.name if c.isupper())
            # TODO 
            # Split into words and count properly capitalized first letters
            # new_proper_caps = sum(
            #     1 for word in suborg.name.split() 
            #     if word and word[0].isupper()
            # )
            # current_proper_caps = sum(
            #     1 for word in current_best.name.split() 
            #     if word and word[0].isupper()
            # )
            # new_has_better_caps = new_proper_caps > current_proper_caps

            if new_has_fewer_spaces or new_has_more_capitals:
                # New suborg is better - demote the old one to the delete list
                duplicates[normalized_name]["delete"].append(current_best)
                duplicates[normalized_name]["keep"] = suborg
            else:
                # If it is not better, just delete the old one
                duplicates[normalized_name]["delete"].append(suborg)

        # Filter out entries without duplicates
        duplicates = {k: v for k, v in duplicates.items() if v.get("delete")}
        if not duplicates:
            logger.info(f"No duplicate suborganizations found.")
            return

        # Show preview of changes
        preview = "The following duplicates will be removed:\n"
        for data in duplicates.values():
            best = data.get("keep")
            preview += f"\nKeeping: '{best.name}' (id: {best.id})"
            
            for duplicate in data.get("delete"):
                preview += f"\nRemoving: '{duplicate.name}' (id: {duplicate.id})"
            preview += "\n"

        # Get confirmation and execute deletions
        if TerminalHelper.prompt_for_execution(
            system_exit_on_terminate=True,
            prompt_message=preview,
            prompt_title="Clean up duplicate suborganizations?",
            verify_message="*** WARNING: This will delete suborganizations! ***"
        ):
            # Update all references to point to the right suborg before deletion
            for record in duplicates.values():
                best_record = record.get("keep")
                delete_ids = [dupe.id for dupe in record.get("delete")]
                
                # Update domain requests
                DomainRequest.objects.filter(
                    sub_organization_id__in=delete_ids
                ).update(sub_organization=best_record)
                
                # Update domain information
                DomainInformation.objects.filter(
                    sub_organization_id__in=delete_ids
                ).update(sub_organization=best_record)

            records_to_delete = set(
                dupe.id 
                for data in duplicates.values() 
                for dupe in data["delete"]
            )
            return records_to_delete
        else:
            return set()
