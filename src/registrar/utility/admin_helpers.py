from registrar.models.domain_request import DomainRequest
from django.template.loader import get_template


def get_all_action_needed_reason_emails(request, domain_request):
    """Returns a dictionary of every action needed reason and its associated email
    for this particular domain request."""

    emails = {}
    for action_needed_reason in domain_request.ActionNeededReasons:
        # Map the action_needed_reason to its default email
        emails[action_needed_reason.value] = get_action_needed_reason_default_email(
            request, domain_request, action_needed_reason.value
        )

    return emails


def get_action_needed_reason_default_email(request, domain_request, action_needed_reason):
    """Returns the default email associated with the given action needed reason"""
    if not action_needed_reason or action_needed_reason == DomainRequest.ActionNeededReasons.OTHER:
        return None

    recipient = domain_request.creator
    # Return the context of the rendered views
    context = {"domain_request": domain_request, "recipient": recipient}

    # Get the email body
    template_path = f"emails/action_needed_reasons/{action_needed_reason}.txt"

    email_body_text = get_template(template_path).render(context=context)
    email_body_text_cleaned = None
    if email_body_text:
        email_body_text_cleaned = email_body_text.strip().lstrip("\n")

    return email_body_text_cleaned
