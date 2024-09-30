from registrar.models.domain_request import DomainRequest
from django.template.loader import get_template
from django.utils.html import format_html
from django.urls import reverse
from django.utils.html import escape
from registrar.models.utility.generic_helper import value_of_attribute


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


def get_field_links_as_list(
        queryset, model_name, attribute_name=None, link_info_attribute=None, separator=None
    ):
        """
        Generate HTML links for items in a queryset, using a specified attribute for link text.

        Args:
            queryset: The queryset of items to generate links for.
            model_name: The model name used to construct the admin change URL.
            attribute_name: The attribute or method name to use for link text. If None, the item itself is used.
            link_info_attribute: Appends f"({value_of_attribute})" to the end of the link.
            separator: The separator to use between links in the resulting HTML.
            If none, an unordered list is returned.

        Returns:
            A formatted HTML string with links to the admin change pages for each item.
        """
        links = []
        for item in queryset:

            # This allows you to pass in attribute_name="get_full_name" for instance.
            if attribute_name:
                item_display_value = value_of_attribute(item, attribute_name)
            else:
                item_display_value = item

            if item_display_value:
                change_url = reverse(f"admin:registrar_{model_name}_change", args=[item.pk])

                link = f'<a href="{change_url}">{escape(item_display_value)}</a>'
                if link_info_attribute:
                    link += f" ({value_of_attribute(item, link_info_attribute)})"

                if separator:
                    links.append(link)
                else:
                    links.append(f"<li>{link}</li>")

        # If no separator is specified, just return an unordered list.
        if separator:
            return format_html(separator.join(links)) if links else "-"
        else:
            links = "".join(links)
            return format_html(f'<ul class="add-list-reset">{links}</ul>') if links else "-"

