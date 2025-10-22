# registrar/signals.py
from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import UserDomainRole, DomainInvitation, User


@receiver(post_delete, sender=UserDomainRole)
def cleanup_retrieved_domain_invitations(sender, instance, **kwargs):
    """
    Safely clean up retrieved domain invitations when a UserDomainRole is deleted.
    Avoid dereferencing related objects that may already be deleted in cascades.
    """
    email = None
    if getattr(instance, "user_id", None):
        email = User.objects.filter(pk=instance.user_id).values_list("email", flat=True).first()

    if not email:
        return

    DomainInvitation.objects.filter(
        email=email,
        domain_id=instance.domain_id,
        status=DomainInvitation.DomainInvitationStatus.RETRIEVED,
    ).delete()
