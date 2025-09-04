from registrar.models.domain_request import DomainRequest
from django.conf import settings
from django.template.loader import get_template
from django.utils.html import format_html
from django.urls import reverse
from django.utils.html import escape
from registrar.models.utility.generic_helper import value_of_attribute
from django.contrib.admin.widgets import AutocompleteSelect


def get_action_needed_reason_default_email(domain_request, action_needed_reason):
    """Returns the default email associated with the given action needed reason"""
    return _get_default_email(
        domain_request,
        file_path=f"emails/action_needed_reasons/{action_needed_reason}.txt",
        reason=action_needed_reason,
        excluded_reasons=[DomainRequest.ActionNeededReasons.OTHER],
    )


def get_rejection_reason_default_email(domain_request, rejection_reason):
    """Returns the default email associated with the given rejection reason"""
    return _get_default_email(
        domain_request,
        file_path="emails/status_change_rejected.txt",
        reason=rejection_reason,
        # excluded_reasons=[DomainRequest.RejectionReasons.OTHER]
    )


def _get_default_email(domain_request, file_path, reason, excluded_reasons=None):
    if not reason:
        return None

    if excluded_reasons and reason in excluded_reasons:
        return None

    recipient = domain_request.requester
    env_base_url = settings.BASE_URL
    # If NOT in prod, update instances of "manage.get.gov" links to point to
    # current environment, ie "getgov-rh.app.cloud.gov"
    manage_url = env_base_url if not settings.IS_PRODUCTION else "https://manage.get.gov"

    # Return the context of the rendered views
    context = {"domain_request": domain_request, "recipient": recipient, "reason": reason, "manage_url": manage_url}

    email_body_text = get_template(file_path).render(context=context)
    email_body_text_cleaned = email_body_text.strip().lstrip("\n") if email_body_text else None

    return email_body_text_cleaned


def get_field_links_as_list(
    queryset,
    model_name,
    attribute_name=None,
    link_info_attribute=None,
    separator=None,
    msg_for_none="-",
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
        msg_for_none: What to return when the field would otherwise display None.
        Defaults to `-`.

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
        return format_html(separator.join(links)) if links else msg_for_none
    else:
        links = "".join(links)
        return format_html(f'<ul class="add-list-reset">{links}</ul>') if links else msg_for_none


class AutocompleteSelectWithPlaceholder(AutocompleteSelect):
    """Override of the default autoselect element. This is because by default,
    the autocomplete element clears data-placeholder"""

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs=extra_attrs)
        if "data-placeholder" in base_attrs:
            attrs["data-placeholder"] = base_attrs["data-placeholder"]
        return attrs

    def __init__(self, field, admin_site, attrs=None, choices=(), using=None):
        """Set a custom ajax url for the select2 if passed through attrs"""
        if attrs:
            self.custom_ajax_url = attrs.pop("ajax-url", None)
        super().__init__(field, admin_site, attrs, choices, using)

    def get_url(self):
        """Override the get_url method to use the custom ajax url"""
        if self.custom_ajax_url:
            return reverse(self.custom_ajax_url)
        return reverse(self.url_name % self.admin_site.name)
