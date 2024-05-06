"""This file contains general purpose helpers that don't belong in any specific location"""

import time
import logging


logger = logging.getLogger(__name__)


class Timer:
    """
    This class is used to measure execution time for performance profiling.
    __enter__ and __exit__ is used such that you can wrap any code you want
    around a with statement. After this exits, logger.info will print
    the execution time in seconds.

    Note that this class does not account for general randomness as more
    robust libraries do, so there is some tiny amount of latency involved
    in using this, but it is minimal enough that for most applications it is not
    noticable.

    Usage:
    with Timer():
        ...some code
    """

    def __enter__(self):
        """Starts the timer"""
        self.start = time.time()
        # This allows usage of the instance within the with block
        return self

    def __exit__(self, *args):
        """Ends the timer and logs what happened"""
        self.end = time.time()
        self.duration = self.end - self.start
        logger.info(f"Execution time: {self.duration} seconds")


class CreateOrUpdateOrganizationTypeHelper:
    """
    A helper that manages the "organization_type" field in DomainRequest and DomainInformation
    """

    def __init__(self, sender, instance, generic_org_to_org_map, election_org_to_generic_org_map):
        # The "model type"
        self.sender = sender
        self.instance = instance
        self.generic_org_map = generic_org_to_org_map
        self.election_org_map = election_org_to_generic_org_map

    def create_or_update_organization_type(self, force_update=False):
        # A new record is added with organization_type not defined.
        # This happens from the regular domain request flow.
        is_new_instance = self.instance.id is None
        if is_new_instance:
            self.handle_new_instance()
        else:
            self.handle_existing_instance(force_update)

        return self.instance

    def handle_new_instance(self):
        """
        If we're creating a new record, try to sync the
        organization_type, generic_org_type, and is_election_board fields.
        """
        org_type_is_none = self.instance.organization_type is None
        generic_org_type_is_none = self.instance.generic_org_type is None

        both_none = org_type_is_none and generic_org_type_is_none
        both_not_none = not org_type_is_none and not generic_org_type_is_none

        # We cannot update both fields at the same time.
        # And we also cannot update no fields at all.
        # We can only update one or the other
        if both_none:
            should_proceed = False
        elif both_not_none:
            # If data exists already for org type and generic org type,
            # we can only update if all data matches.
            # Otherwise, which one do we sync with?
            should_proceed = self._check_new_instance_values()
        else:
            # This means that we're only updating one field at a time.
            # Either generic_org_type/is_election_office OR organization_type.
            # but not both.
            should_proceed = True

        if should_proceed:
            self._update_fields(org_type_is_none, generic_org_type_is_none)
        else:
            logger.debug("handle_new_instance() -> Skipping org update for new instance")

    def handle_existing_instance(self, force_update_when_no_are_changes_found=False):
        """
        If we're updating a record, try to sync the
        organization_type, generic_org_type, and is_election_board fields.
        """
        # Check the new and old values
        generic_org_changed, election_board_changed, org_type_changed = self._get_fields_that_were_changed()

        # Check for what fields need to be updated
        organization_type_needs_update = generic_org_changed or election_board_changed
        generic_org_type_needs_update = org_type_changed

        both_need_update = generic_org_type_needs_update and organization_type_needs_update
        both_dont_need_update = not generic_org_type_needs_update and not organization_type_needs_update

        if both_need_update:
            raise ValueError("Cannot update organization_type and generic_org_type simultaneously.")
        elif both_dont_need_update:
            if force_update_when_no_are_changes_found:
                # Pretend that this instance is a new instance (i.e. - overwrite data)
                # Useful for scripts. Otherwise, lets avoid this.
                self.handle_new_instance()
            else:
                logger.debug(f"handle_existing_instance() -> No changes made.")
        else:
            self._update_fields(organization_type_needs_update, generic_org_type_needs_update)

    def _get_fields_that_were_changed(self):
        """
        Compare what is changing from the old instance to the new one
        """
        current_instance = self.sender.objects.get(id=self.instance.id)

        # Check the new and old values
        generic_org_type_changed = self.instance.generic_org_type != current_instance.generic_org_type
        is_election_board_changed = self.instance.is_election_board != current_instance.is_election_board
        organization_type_changed = self.instance.organization_type != current_instance.organization_type

        return (generic_org_type_changed, is_election_board_changed, organization_type_changed)

    def _update_fields(self, organization_type_needs_update, generic_org_type_needs_update):
        if organization_type_needs_update and generic_org_type_needs_update:
            raise ValueError("Cannot update both org type and generic org type at the same time.")
        elif organization_type_needs_update:
            self._update_org_type_from_generic_org_and_election()
        elif generic_org_type_needs_update:
            self._update_generic_org_and_election_from_org_type()
        else:
            logger.debug(f"_update_fields() -> No fields to update.")

    def _update_org_type_from_generic_org_and_election(self):
        """Given a field values for generic_org_type and is_election_board, update the
        organization_type field."""

        # We convert to a string because the enum types are different.
        generic_org_type = str(self.instance.generic_org_type)
        can_have_election_board = generic_org_type in self.generic_org_map

        new_org = generic_org_type
        if can_have_election_board:
            # If this domain can have an election board, swap to the election board "type"
            # If it can have one but the is_election_board value is None, this means "False"
            new_org = self.generic_org_map[generic_org_type] if self.instance.is_election_board is not None else False  # noqa
        elif self.instance.is_election_board is not None:
            # If we can't have an election board, is_election_board should be None
            self.instance.is_election_board = None
        else:
            # Do nothing - this means that we can't have an election board
            # and the is_election_board value = None.
            # For instance - this could be a federal domain with is_election_board = None
            pass

        self.instance.organization_type = new_org

    def _update_generic_org_and_election_from_org_type(self):
        """Given the field value for organization_type, update the
        generic_org_type and is_election_board field."""

        # We convert to a string because the enum types are different
        # between OrgChoicesElectionOffice and OrganizationChoices.
        # But their names are the same (for the most part).
        current_org = str(self.instance.organization_type)
        has_election_board = current_org in self.election_org_map
        can_have_election_board = current_org in self.generic_org_map

        if self.instance.organization_type is None:
            self.instance.generic_org_type = None
        else:
            new_org = current_org
            if has_election_board:
                new_org = self.election_org_map[current_org]

            self.instance.generic_org_type = new_org

        self.instance.is_election_board = (
            has_election_board if can_have_election_board else None
        )

    def _check_new_instance_values(self) -> bool:
        org_type = str(self.instance.organization_type)

        # Strip "_election" from organization_type if it exists
        cleaned_org_type = self.election_org_map.get(org_type)

        # Does the underlying org type on generic_org_type match whats on organization_type?
        org_out_of_sync = str(self.instance.generic_org_type) != cleaned_org_type

        # Does the underlying election type match whats on organization_type?
        is_election_type = "_election" in org_type
        election_type_out_of_sync = is_election_type != self.instance.is_election_board
        can_have_election_board = org_type in self.generic_org_map

        # Check if allowing this update would override any data.
        # We want to avoid this because we want to avoid recursively updating each field forever.
        # (organization_type => generic_org_type => organization_type) etc. They MUST match.
        would_override_org = org_out_of_sync and cleaned_org_type is not None
        would_override_election_type = election_type_out_of_sync and can_have_election_board

        if would_override_org:
            message = (
                "Cannot add organization_type and generic_org_type simultaneously. "
                "generic_org_type and organization_type fields do not match (would override data)."
            )
            raise ValueError(message)
        elif would_override_election_type:
            message = (
                "Cannot add organization_type and is_election_board simultaneously. "
                "is_election_board fields do not match (would override data)."
            )
            raise ValueError(message)
        else:
            return True
