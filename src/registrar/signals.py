import logging

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from .models import User, Contact, DomainRequest, DomainInformation


logger = logging.getLogger(__name__)


@receiver(pre_save, sender=DomainRequest)
@receiver(pre_save, sender=DomainInformation)
def create_or_update_organization_type(sender, instance, **kwargs):
    """The organization_type field on DomainRequest and DomainInformation is consituted from the
    generic_org_type and is_election_board fields. To keep the organization_type
    field up to date, we need to update it before save based off of those field
    values.

    If the instance is marked as an election board and the generic_org_type is not
    one of the excluded types (FEDERAL, INTERSTATE, SCHOOL_DISTRICT), the
    organization_type is set to a corresponding election variant. Otherwise, it directly
    mirrors the generic_org_type value.
    """

    # == Init variables == #
    election_org_choices = DomainRequest.OrgChoicesElectionOffice

    # For any given organization type, return the "_election" variant.
    # For example: STATE_OR_TERRITORY => STATE_OR_TERRITORY_ELECTION
    generic_org_to_org_map = election_org_choices.get_org_generic_to_org_election()

    # For any given "_election" variant, return the base org type.
    # For example: STATE_OR_TERRITORY_ELECTION => STATE_OR_TERRITORY
    election_org_to_generic_org_map = election_org_choices.get_org_election_to_org_generic()

    # A new record is added with organization_type not defined.
    # This happens from the regular domain request flow.
    is_new_instance = instance.id is None

    if is_new_instance:

        # == Check for invalid conditions before proceeding == #
        should_proceed = _validate_new_instance(instance, election_org_to_generic_org_map, generic_org_to_org_map)
        if not should_proceed:
            return None
        # == Program flow will halt here if there is no reason to update == #

        # == Update the linked values == #
        organization_type_needs_update = instance.organization_type is None
        generic_org_type_needs_update = instance.generic_org_type is None

        # If a field is none, it indicates (per prior checks) that the
        # related field (generic org type <-> org type) has data and we should update according to that.
        if organization_type_needs_update:
            _update_org_type_from_generic_org_and_election(instance, generic_org_to_org_map)
        elif generic_org_type_needs_update:
            _update_generic_org_and_election_from_org_type(
                instance, election_org_to_generic_org_map, generic_org_to_org_map
            )
    else:

        # == Init variables == #
        # Instance is already in the database, fetch its current state
        current_instance = DomainRequest.objects.get(id=instance.id)

        # Check the new and old values
        generic_org_type_changed = instance.generic_org_type != current_instance.generic_org_type
        is_election_board_changed = instance.is_election_board != current_instance.is_election_board
        organization_type_changed = instance.organization_type != current_instance.organization_type

        # == Check for invalid conditions before proceeding == #
        if organization_type_changed and (generic_org_type_changed or is_election_board_changed):
            # Since organization type is linked with generic_org_type and election board,
            # we have to update one or the other, not both.
            # This will not happen in normal flow as it is not possible otherwise.
            raise ValueError("Cannot update organization_type and generic_org_type simultaneously.")
        elif not organization_type_changed and (not generic_org_type_changed and not is_election_board_changed):
            # Do values to update - do nothing
            return None
        # == Program flow will halt here if there is no reason to update == #

        # == Update the linked values == #
        # Find out which field needs updating
        organization_type_needs_update = generic_org_type_changed or is_election_board_changed
        generic_org_type_needs_update = organization_type_changed

        # Update that field
        if organization_type_needs_update:
            _update_org_type_from_generic_org_and_election(instance, generic_org_to_org_map)
        elif generic_org_type_needs_update:
            _update_generic_org_and_election_from_org_type(
                instance, election_org_to_generic_org_map, generic_org_to_org_map
            )


def _update_org_type_from_generic_org_and_election(instance, org_map):
    """Given a field values for generic_org_type and is_election_board, update the
    organization_type field."""

    # We convert to a string because the enum types are different.
    generic_org_type = str(instance.generic_org_type)

    # If the election board is none, then it tells us that it is an invalid field.
    # Such as federal, interstate, or school_district.
    if instance.is_election_board is None and generic_org_type not in org_map:
        instance.organization_type = generic_org_type
        return instance
    elif instance.is_election_board is None and generic_org_type in org_map:
        # This can only happen with manual data tinkering, which causes these to be out of sync.
        instance.is_election_board = False
        logger.warning("create_or_update_organization_type() -> is_election_board is out of sync. Updating value.")

    if generic_org_type in org_map:
        # Swap to the election type if it is an election board. Otherwise, stick to the normal one.
        instance.organization_type = org_map[generic_org_type] if instance.is_election_board else generic_org_type
    else:
        # Election board should be reset to None if the record
        # can't have one. For example, federal.
        instance.organization_type = generic_org_type
        instance.is_election_board = None


def _update_generic_org_and_election_from_org_type(instance, election_org_map, generic_org_map):
    """Given the field value for organization_type, update the
    generic_org_type and is_election_board field."""

    # We convert to a string because the enum types are different
    # between OrgChoicesElectionOffice and OrganizationChoices.
    # But their names are the same (for the most part).
    current_org_type = str(instance.organization_type)

    # This essentially means: "_election" in current_org_type.
    if current_org_type in election_org_map:
        new_org = election_org_map[current_org_type]
        instance.generic_org_type = new_org
        instance.is_election_board = True
    else:
        instance.generic_org_type = current_org_type

        # This basically checks if the given org type
        # can even have an election board in the first place.
        # For instance, federal cannot so is_election_board = None
        if current_org_type in generic_org_map:
            instance.is_election_board = False
        else:
            instance.is_election_board = None


def _validate_new_instance(instance, election_org_to_generic_org_map, generic_org_to_org_map):
    """
    Validates whether a new instance of DomainRequest or DomainInformation can proceed with the update
    based on the consistency between organization_type, generic_org_type, and is_election_board.

    Returns a boolean determining if execution should proceed or not.
    """

    # We conditionally accept both of these values to exist simultaneously, as long as
    # those values do not intefere with eachother.
    # Because this condition can only be triggered through a dev (no user flow),
    # we throw an error if an invalid state is found here.
    if instance.organization_type and instance.generic_org_type:
        generic_org_type = str(instance.generic_org_type)
        organization_type = str(instance.organization_type)

        # Strip "_election" if it exists
        mapped_org_type = election_org_to_generic_org_map.get(organization_type)

        # Do tests on the org update for election board changes.
        is_election_type = "_election" in organization_type
        can_have_election_board = organization_type in generic_org_to_org_map

        election_board_mismatch = (is_election_type != instance.is_election_board) and can_have_election_board
        org_type_mismatch = mapped_org_type is not None and (generic_org_type != mapped_org_type)
        if election_board_mismatch or org_type_mismatch:
            message = (
                "Cannot add organization_type and generic_org_type simultaneously "
                "when generic_org_type, is_election_board, and organization_type values do not match."
            )
            raise ValueError(message)

        return True
    elif not instance.organization_type and not instance.generic_org_type:
        return False
    else:
        return True


@receiver(post_save, sender=User)
def handle_profile(sender, instance, **kwargs):
    """Method for when a User is saved.

    A first time registrant may have been invited, so we'll search for a matching
    Contact record, by email address, and associate them, if possible.

    A first time registrant may not have a matching Contact, so we'll create one,
    copying the contact values we received from Login.gov in order to initialize it.

    During subsequent login, a User record may be updated with new data from Login.gov,
    but in no case will we update contact values on an existing Contact record.
    """

    first_name = getattr(instance, "first_name", "")
    last_name = getattr(instance, "last_name", "")
    email = getattr(instance, "email", "")
    phone = getattr(instance, "phone", "")

    is_new_user = kwargs.get("created", False)

    if is_new_user:
        contacts = Contact.objects.filter(email=email)
    else:
        contacts = Contact.objects.filter(user=instance)

    if len(contacts) == 0:  # no matching contact
        Contact.objects.create(
            user=instance,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
        )

    if len(contacts) >= 1 and is_new_user:  # a matching contact
        contacts[0].user = instance
        contacts[0].save()

        if len(contacts) > 1:  # multiple matches
            logger.warning(
                "There are multiple Contacts with the same email address."
                f" Picking #{contacts[0].id} for User #{instance.id}."
            )
