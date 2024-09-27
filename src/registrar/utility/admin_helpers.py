from registrar.models.domain_request import DomainRequest
from django.template.loader import get_template


def get_all_action_needed_reason_emails(domain_request):
    """Returns a dictionary of every action needed reason and its associated email
    for this particular domain request."""
    return _get_all_default_emails(
        reasons=DomainRequest.ActionNeededReasons,
        # Where the emails are stored. This assumes that it contains a list of .txt files with the reason. 
        path_root="emails/action_needed_reasons",
        # What reasons don't send out emails (none is handled automagically)
        excluded_reasons=[DomainRequest.ActionNeededReasons.OTHER],
        # Who to send it to, and from what domain request to reference
        domain_request=domain_request
    )


def get_action_needed_reason_default_email(domain_request, action_needed_reason):
    """Returns the default email associated with the given action needed reason"""
    return _get_default_email(
        domain_request,
        path_root="emails/action_needed_reasons",
        reason=action_needed_reason,
        excluded_reasons=[DomainRequest.ActionNeededReasons.OTHER]
    )


def get_all_rejection_reason_emails(domain_request):
    """Returns a dictionary of every rejection reason and its associated email
    for this particular domain request."""
    return _get_all_default_emails(
        reasons=DomainRequest.RejectionReasons,
        # Where the emails are stored. This assumes that it contains a list of .txt files with the reason.
        path_root="emails/rejection_reasons",
        # What reasons don't send out emails (none is handled automagically)
        excluded_reasons=[DomainRequest.RejectionReasons.OTHER],
        # Who to send it to, and from what domain request to reference
        domain_request=domain_request
    )


def get_rejection_reason_default_email(domain_request, rejection_reason):
    """Returns the default email associated with the given rejection reason"""
    return _get_default_email(
        domain_request,
        path_root="emails/rejection_reasons",
        reason=rejection_reason,
        excluded_reasons=[DomainRequest.RejectionReasons.OTHER]
    )

def _get_all_default_emails(reasons, path_root, excluded_reasons, domain_request):
    emails = {}
    for reason in reasons:
        # Map the reason to its default email
        emails[reason.value] = _get_default_email(
            domain_request, path_root, reason, excluded_reasons
        )
    return emails

def _get_default_email(domain_request, path_root, reason, excluded_reasons=None):
    if not reason:
        return None

    if excluded_reasons and reason in excluded_reasons:
        return None

    recipient = domain_request.creator
    # Return the context of the rendered views
    context = {"domain_request": domain_request, "recipient": recipient}

    # Get the email body
    template_path = f"{path_root}/{reason}.txt"

    email_body_text = get_template(template_path).render(context=context)
    email_body_text_cleaned = None
    if email_body_text:
        email_body_text_cleaned = email_body_text.strip().lstrip("\n")

    return email_body_text_cleaned
