from registrar.models.domain_request import DomainRequest
from django.template.loader import get_template


def get_action_needed_reason_default_email(domain_request, action_needed_reason):
    """Returns the default email associated with the given action needed reason"""
    return _get_default_email(
        domain_request,
        file_path=f"emails/action_needed_reasons/{action_needed_reason}.txt",
        reason=action_needed_reason,
        excluded_reasons=[DomainRequest.ActionNeededReasons.OTHER]
    )


def get_rejection_reason_default_email(domain_request, rejection_reason):
    """Returns the default email associated with the given rejection reason"""
    return _get_default_email(
        domain_request,
        file_path="emails/status_change_rejected.txt",
        reason=rejection_reason,
        excluded_reasons=[DomainRequest.RejectionReasons.OTHER]
    )

def _get_default_email(domain_request, file_path, reason, excluded_reasons=None):
    if not reason:
        return None

    if excluded_reasons and reason in excluded_reasons:
        return None

    recipient = domain_request.creator
    # Return the context of the rendered views
    context = {"domain_request": domain_request, "recipient": recipient, "reason": reason}

    email_body_text = get_template(file_path).render(context=context)
    email_body_text_cleaned = email_body_text.strip().lstrip("\n") if email_body_text else None

    return email_body_text_cleaned
