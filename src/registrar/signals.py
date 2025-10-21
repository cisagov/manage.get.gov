# registrar/signals.py
import logging
import os
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.db.backends.signals import connection_created
from .models import UserDomainRole, DomainInvitation, User

logger = logging.getLogger("registrar.dbconn")


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


def on_connection_created(sender, connection, **kwargs):
    sd = connection.settings_dict
    logger.info(
        "DB_CONNECTION_CREATED: alias=%s vendor=%s db=%s user=%s host=%s pid=%s",
        connection.alias,
        connection.vendor,
        sd.get("NAME"),
        sd.get("USER"),
        sd.get("HOST"),
        getattr(connection, "get_backend_pid", lambda: None)(),
    )


# Hook up the signal only if toggled on
if os.getenv("LOG_DB_CONNECTIONS", "false").lower() == "true":
    connection_created.connect(on_connection_created)
