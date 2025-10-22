# registrar/signals.py
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import UserDomainRole, DomainInvitation


@receiver(post_delete, sender=UserDomainRole)
def cleanup_retrieved_domain_invitations(sender, instance, **kwargs):
    """
    Automatically clean up retrieved domain invitations when a UserDomainRole is deleted.
    This ensures invitation and permission systems stay synchronized and resolves
    issues where retrieved invitations block re-adding users to domains.
    """
    DomainInvitation.objects.filter(
        email=instance.user.email, domain=instance.domain, status=DomainInvitation.DomainInvitationStatus.RETRIEVED
    ).delete()
