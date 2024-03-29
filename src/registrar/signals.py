import logging

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from .models import User, Contact, DomainRequest


logger = logging.getLogger(__name__)


@receiver(pre_save, sender=DomainRequest)
def create_or_update_organization_type(sender, instance, **kwargs):
    """The organization_type field on DomainRequest is consituted from the
    generic_org_type and is_election_board fields. To keep the organization_type
    field up to date, we need to update it before save based off of those field
    values.

    If the instance is marked as an election board and the generic_org_type is not
    one of the excluded types (FEDERAL, INTERSTATE, SCHOOL_DISTRICT), the
    organization_type is set to a corresponding election variant. Otherwise, it directly
    mirrors the generic_org_type value.
    """
    if not isinstance(instance, DomainRequest):
        # I don't see how this could possibly happen - but its still a good check to have.
        # Lets force a fail condition rather than wait for one to happen, if this occurs.
        raise ValueError("Type mismatch. The instance was not DomainRequest.")

    # == Init variables == #
    # We can't grab the election variant if it is in federal, interstate, or school_district.
    # The "election variant" is just the org name, with " - Election" appended to the end.
    # For example, "School district - Election".
    invalid_types = [
        DomainRequest.OrganizationChoices.FEDERAL,
        DomainRequest.OrganizationChoices.INTERSTATE,
        DomainRequest.OrganizationChoices.SCHOOL_DISTRICT,
    ]

    # TODO - maybe we need a check here for .filter then .get
    is_new_instance = instance.id is None

    # A new record is added with organization_type not defined.
    # This happens from the regular domain request flow.
    if is_new_instance:

        # == Check for invalid conditions before proceeding == #
        if instance.organization_type and instance.generic_org_type:
            # Since organization type is linked with generic_org_type and election board,
            # we have to update one or the other, not both.
            raise ValueError("Cannot update organization_type and generic_org_type simultaneously.")    
        elif not instance.organization_type and not instance.generic_org_type:
            # Do values to update - do nothing
            return None
        # == Program flow will halt here if there is no reason to update == #

        # == Update the linked values == #
        # Find out which field needs updating
        organization_type_needs_update = instance.organization_type is None
        generic_org_type_needs_update = instance.generic_org_type is None

        # Update that field
        if organization_type_needs_update:
            _update_org_type_from_generic_org_and_election(instance, invalid_types)
        elif generic_org_type_needs_update:
            _update_generic_org_and_election_from_org_type(instance)
    else:

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
            _update_org_type_from_generic_org_and_election(instance, invalid_types)
        elif generic_org_type_needs_update:
            _update_generic_org_and_election_from_org_type(instance)

def _update_org_type_from_generic_org_and_election(instance, invalid_types):
    # TODO handle if generic_org_type is None
    if instance.generic_org_type not in invalid_types and instance.is_election_board:
        instance.organization_type = f"{instance.generic_org_type}_election"
    else:
        instance.organization_type = str(instance.generic_org_type)


def _update_generic_org_and_election_from_org_type(instance):
    """Given a value for organization_type, update the
    generic_org_type and is_election_board values."""
    # TODO find a better solution than this
    current_org_type = str(instance.organization_type)
    if "_election" in current_org_type:
        instance.generic_org_type = current_org_type.split("_election")[0]
        instance.is_election_board = True
    else:
        instance.organization_type = str(instance.generic_org_type)
        instance.is_election_board = False

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
