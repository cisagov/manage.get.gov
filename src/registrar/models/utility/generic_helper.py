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
        self.generic_org_to_org_map = generic_org_to_org_map
        self.election_org_to_generic_org_map = election_org_to_generic_org_map

    def create_or_update_organization_type(self, force_update=False):
        """The organization_type field on DomainRequest and DomainInformation is consituted from the
        generic_org_type and is_election_board fields. To keep the organization_type
        field up to date, we need to update it before save based off of those field
        values.

        If the instance is marked as an election board and the generic_org_type is not
        one of the excluded types (FEDERAL, INTERSTATE, SCHOOL_DISTRICT), the
        organization_type is set to a corresponding election variant. Otherwise, it directly
        mirrors the generic_org_type value.

        args:
            force_update (bool): If an existing instance has no values to change,
            try to update the organization_type field (or related fields) anyway.
            This is done by invoking the new instance handler.

            Use to force org type to be updated to the correct value even
            if no other changes were made (including is_election).
        """

        # A new record is added with organization_type not defined.
        # This happens from the regular domain request flow.
        is_new_instance = self.instance.id is None
        if is_new_instance:
            self._handle_new_instance()
        else:
            self._handle_existing_instance(force_update)

        return self.instance

    def _handle_new_instance(self):
        # == Check for invalid conditions before proceeding == #
        should_proceed = self._validate_new_instance()
        if not should_proceed:
            return None
        # == Program flow will halt here if there is no reason to update == #

        # == Update the linked values == #
        organization_type_needs_update = self.instance.organization_type is None
        generic_org_type_needs_update = self.instance.generic_org_type is None

        # If a field is none, it indicates (per prior checks) that the
        # related field (generic org type <-> org type) has data and we should update according to that.
        if organization_type_needs_update:
            self._update_org_type_from_generic_org_and_election()
        elif generic_org_type_needs_update:
            self._update_generic_org_and_election_from_org_type()

        # Update the field
        self._update_fields(organization_type_needs_update, generic_org_type_needs_update)

    def _handle_existing_instance(self, force_update_when_no_are_changes_found=False):
        # == Init variables == #
        # Instance is already in the database, fetch its current state
        current_instance = self.sender.objects.get(id=self.instance.id)

        # Check the new and old values
        generic_org_type_changed = self.instance.generic_org_type != current_instance.generic_org_type
        is_election_board_changed = self.instance.is_election_board != current_instance.is_election_board
        organization_type_changed = self.instance.organization_type != current_instance.organization_type

        # == Check for invalid conditions before proceeding == #
        if organization_type_changed and (generic_org_type_changed or is_election_board_changed):
            # Since organization type is linked with generic_org_type and election board,
            # we have to update one or the other, not both.
            # This will not happen in normal flow as it is not possible otherwise.
            raise ValueError("Cannot update organization_type and generic_org_type simultaneously.")
        elif not organization_type_changed and (not generic_org_type_changed and not is_election_board_changed):
            # No changes found
            if force_update_when_no_are_changes_found:
                # If we want to force an update anyway, we can treat this record like
                # its a new one in that we check for "None" values rather than changes.
                self._handle_new_instance()
        else:
            # == Update the linked values == #
            # Find out which field needs updating
            organization_type_needs_update = generic_org_type_changed or is_election_board_changed
            generic_org_type_needs_update = organization_type_changed

            # Update the field
            self._update_fields(organization_type_needs_update, generic_org_type_needs_update)

    def _update_fields(self, organization_type_needs_update, generic_org_type_needs_update):
        """
        Validates the conditions for updating organization and generic organization types.

        Raises:
            ValueError: If both organization_type_needs_update and generic_org_type_needs_update are True,
                        indicating an attempt to update both fields simultaneously, which is not allowed.
        """
        # We shouldn't update both of these at the same time.
        # It is more useful to have these as seperate variables, but it does impose
        # this restraint.
        if organization_type_needs_update and generic_org_type_needs_update:
            raise ValueError("Cannot update both org type and generic org type at the same time.")

        if organization_type_needs_update:
            self._update_org_type_from_generic_org_and_election()
        elif generic_org_type_needs_update:
            self._update_generic_org_and_election_from_org_type()

    def _update_org_type_from_generic_org_and_election(self):
        """Given a field values for generic_org_type and is_election_board, update the
        organization_type field."""

        # We convert to a string because the enum types are different.
        generic_org_type = str(self.instance.generic_org_type)
        if generic_org_type not in self.generic_org_to_org_map:
            # Election board should always be reset to None if the record
            # can't have one. For example, federal.
            if self.instance.is_election_board is not None:
                # This maintains data consistency.
                # There is no avenue for this to occur in the UI,
                # as such - this can only occur if the object is initialized in this way.
                # Or if there are pre-existing data.
                logger.debug(
                    "create_or_update_organization_type() -> is_election_board "
                    f"cannot exist for {generic_org_type}. Setting to None."
                )
                self.instance.is_election_board = None
            self.instance.organization_type = generic_org_type
        else:
            # This can only happen with manual data tinkering, which causes these to be out of sync.
            if self.instance.is_election_board is None:
                logger.warning(
                    "create_or_update_organization_type() -> is_election_board is out of sync. Updating value."
                )
                self.instance.is_election_board = False

            if self.instance.is_election_board:
                self.instance.organization_type = self.generic_org_to_org_map[generic_org_type]
            else:
                self.instance.organization_type = generic_org_type

    def _update_generic_org_and_election_from_org_type(self):
        """Given the field value for organization_type, update the
        generic_org_type and is_election_board field."""

        # We convert to a string because the enum types are different
        # between OrgChoicesElectionOffice and OrganizationChoices.
        # But their names are the same (for the most part).
        current_org_type = str(self.instance.organization_type)
        election_org_map = self.election_org_to_generic_org_map
        generic_org_map = self.generic_org_to_org_map

        # This essentially means: "_election" in current_org_type.
        if current_org_type in election_org_map:
            new_org = election_org_map[current_org_type]
            self.instance.generic_org_type = new_org
            self.instance.is_election_board = True
        elif self.instance.organization_type is not None:
            self.instance.generic_org_type = current_org_type

            # This basically checks if the given org type
            # can even have an election board in the first place.
            # For instance, federal cannot so is_election_board = None
            if current_org_type in generic_org_map:
                self.instance.is_election_board = False
            else:
                # This maintains data consistency.
                # There is no avenue for this to occur in the UI,
                # as such - this can only occur if the object is initialized in this way.
                # Or if there are pre-existing data.
                logger.warning(
                    "create_or_update_organization_type() -> is_election_board "
                    f"cannot exist for {current_org_type}. Setting to None."
                )
                self.instance.is_election_board = None
        else:
            # if self.instance.organization_type is set to None, then this means
            # we should clear the related fields.
            # This will not occur if it just is None (i.e. default), only if it is set to be so.
            self.instance.is_election_board = None
            self.instance.generic_org_type = None

    def _validate_new_instance(self):
        """
        Validates whether a new instance of DomainRequest or DomainInformation can proceed with the update
        based on the consistency between organization_type, generic_org_type, and is_election_board.

        Returns a boolean determining if execution should proceed or not.
        """

        # We conditionally accept both of these values to exist simultaneously, as long as
        # those values do not intefere with eachother.
        # Because this condition can only be triggered through a dev (no user flow),
        # we throw an error if an invalid state is found here.
        if self.instance.organization_type and self.instance.generic_org_type:
            generic_org_type = str(self.instance.generic_org_type)
            organization_type = str(self.instance.organization_type)

            # Strip "_election" if it exists
            mapped_org_type = self.election_org_to_generic_org_map.get(organization_type)

            # Do tests on the org update for election board changes.
            is_election_type = "_election" in organization_type
            can_have_election_board = organization_type in self.generic_org_to_org_map

            election_board_mismatch = (is_election_type != self.instance.is_election_board) and can_have_election_board
            org_type_mismatch = mapped_org_type is not None and (generic_org_type != mapped_org_type)
            if election_board_mismatch or org_type_mismatch:
                message = (
                    "Cannot add organization_type and generic_org_type simultaneously "
                    "when generic_org_type, is_election_board, and organization_type values do not match."
                )
                raise ValueError(message)

            return True
        elif not self.instance.organization_type and not self.instance.generic_org_type:
            return False
        else:
            return True


def to_database(form, obj):
    """
    Adds the form's cleaned data to `obj` and saves `obj`.

    Does nothing if form is not valid.
    """
    if not form.is_valid():
        return None
    for name, value in form.cleaned_data.items():
        setattr(obj, name, value)
    obj.save()


def from_database(form_class, obj):
    """Returns a dict of form field values gotten from `obj`."""
    if obj is None:
        return {}
    return {name: getattr(obj, name) for name in form_class.declared_fields.keys()}  # type: ignore