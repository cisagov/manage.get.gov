import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User, Contact


logger = logging.getLogger(__name__)


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
    logger.info(f'in handle_profile first {instance}')

    is_new_user = kwargs.get("created", False)

    if is_new_user:
        contacts = Contact.objects.filter(email=email)
    else:
        contacts = Contact.objects.filter(user=instance)

    if len(contacts) == 0:  # no matching contact
        logger.info(f'inside no matching contacts for first {first_name} last {last_name} email {email}')
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
