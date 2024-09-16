import logging

from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from registrar.models.domain import Domain
from registrar.models.domain_information import DomainInformation
from registrar.models.domain_request import DomainRequest
from registrar.models.portfolio import Portfolio
from registrar.models.user import User
from django.contrib.admin import site
from django.contrib import messages

from registrar.models.user_domain_role import UserDomainRole
from registrar.models.user_portfolio_permission import UserPortfolioPermission
from registrar.models.verified_by_staff import VerifiedByStaff
from typing import Any, List

logger = logging.getLogger(__name__)


class TransferUserView(View):
    """Transfer user methods that set up the transfer_user template and handle the forms on it."""

    JOINS = [
        (DomainRequest, "creator"),
        (DomainInformation, "creator"),
        (Portfolio, "creator"),
        (DomainRequest, "investigator"),
        (UserDomainRole, "user"),
        (VerifiedByStaff, "requestor"),
        (UserPortfolioPermission, "user"),
    ]

    # Future-proofing in case joined fields get added on the user model side
    # This was tested in the first portfolio model iteration and works
    USER_FIELDS: List[Any] = []

    def get(self, request, user_id):
        """current_user referes to the 'source' user where the button that redirects to this view was clicked.
        other_users exclude current_user and populate a dropdown, selected_user is the selection in the dropdown.

        This also querries the relevant domains and domain requests, and the admin context needed for the sidenav."""

        current_user = get_object_or_404(User, pk=user_id)
        other_users = User.objects.exclude(pk=user_id).order_by(
            "first_name", "last_name"
        )  # Exclude the current user from the dropdown

        # Get the default admin site context, needed for the sidenav
        admin_context = site.each_context(request)

        context = {
            "current_user": current_user,
            "other_users": other_users,
            "logged_in_user": request.user,
            **admin_context,  # Include the admin context
            "current_user_domains": self.get_domains(current_user),
            "current_user_domain_requests": self.get_domain_requests(current_user),
            "current_user_portfolios": self.get_portfolios(current_user),
        }

        selected_user_id = request.GET.get("selected_user")
        if selected_user_id:
            selected_user = get_object_or_404(User, pk=selected_user_id)
            context["selected_user"] = selected_user
            context["selected_user_domains"] = self.get_domains(selected_user)
            context["selected_user_domain_requests"] = self.get_domain_requests(selected_user)
            context["selected_user_portfolios"] = self.get_portfolios(selected_user)

        return render(request, "admin/transfer_user.html", context)

    def post(self, request, user_id):
        """This handles the transfer from selected_user to current_user then deletes selected_user.

        NOTE: We have a ticket to refactor this into a more solid lookup for related fields in #2645"""

        current_user = get_object_or_404(User, pk=user_id)
        selected_user_id = request.POST.get("selected_user")
        selected_user = get_object_or_404(User, pk=selected_user_id)

        try:
            change_logs = []

            # Transfer specific fields
            self.transfer_user_fields_and_log(selected_user, current_user, change_logs)

            # Perform the updates and log the changes
            for model_class, field_name in self.JOINS:
                self.update_joins_and_log(model_class, field_name, selected_user, current_user, change_logs)

            # Success message if any related objects were updated
            if change_logs:
                success_message = f"Data transferred successfully for the following objects: {change_logs}"
                messages.success(request, success_message)

            selected_user.delete()
            messages.success(request, f"Deleted {selected_user} {selected_user.username}")

        except Exception as e:
            messages.error(request, f"An error occurred during the transfer: {e}")

        return redirect("admin:registrar_user_change", object_id=user_id)

    @classmethod
    def update_joins_and_log(cls, model_class, field_name, selected_user, current_user, change_logs):
        """
        Helper function to update the user join fields for a given model and log the changes.
        """

        filter_kwargs = {field_name: selected_user}
        updated_objects = model_class.objects.filter(**filter_kwargs)

        for obj in updated_objects:
            # Check for duplicate UserDomainRole before updating
            if model_class == UserDomainRole:
                if model_class.objects.filter(user=current_user, domain=obj.domain).exists():
                    continue  # Skip the update to avoid a duplicate

            # Update the field on the object and save it
            setattr(obj, field_name, current_user)
            obj.save()

            # Log the change
            cls.log_change(obj, field_name, selected_user, current_user, change_logs)

    @classmethod
    def transfer_user_fields_and_log(cls, selected_user, current_user, change_logs):
        """
        Transfers portfolio fields from the selected_user to the current_user.
        Logs the changes for each transferred field.
        """
        for field in cls.USER_FIELDS:
            field_value = getattr(selected_user, field, None)

            if field_value:
                setattr(current_user, field, field_value)
                cls.log_change(current_user, field, field_value, field_value, change_logs)

        current_user.save()

    @classmethod
    def log_change(cls, obj, field_name, field_value, new_value, change_logs):
        """Logs the change for a specific field on an object"""
        log_entry = f'Changed {field_name} from "{field_value}" to "{new_value}" on {obj}'

        logger.info(log_entry)

        # Collect the related object for the success message
        change_logs.append(log_entry)

    @classmethod
    def get_domains(cls, user):
        """A simplified version of domains_json"""
        user_domain_roles = UserDomainRole.objects.filter(user=user)
        domain_ids = user_domain_roles.values_list("domain_id", flat=True)
        domains = Domain.objects.filter(id__in=domain_ids)

        return domains

    @classmethod
    def get_domain_requests(cls, user):
        """A simplified version of domain_requests_json"""
        domain_requests = DomainRequest.objects.filter(creator=user)

        return domain_requests

    @classmethod
    def get_portfolios(cls, user):
        """Get portfolios"""
        portfolios = UserPortfolioPermission.objects.filter(user=user)

        return portfolios
