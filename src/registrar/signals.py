# registrar/signals.py
from django.db.models.signals import post_delete
from django.dispatch import receiver
import logging

from .models import UserDomainRole, DomainInvitation

logger = logging.getLogger(__name__)

@receiver(post_delete, sender=UserDomainRole)
def cleanup_retrieved_domain_invitations(sender, instance, **kwargs):
    """
    Automatically clean up retrieved domain invitations when a UserDomainRole is deleted.
    """
    print(f"🔥 SIGNAL FIRED: UserDomainRole deleted for {instance.user.email} on {instance.domain.name}")
    
    matching_invitations = DomainInvitation.objects.filter(
        email=instance.user.email,
        domain=instance.domain,
        status=DomainInvitation.DomainInvitationStatus.RETRIEVED
    )
    
    count = matching_invitations.count()
    print(f"🧹 Found {count} retrieved invitations to clean up")
    
    if count > 0:
        matching_invitations.delete()
        print(f"✅ Deleted {count} retrieved invitations")
    else:
        print("ℹ️  No retrieved invitations to clean up")