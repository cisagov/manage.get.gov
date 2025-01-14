import logging
from django.db import transaction
from django.db.models import Manager, ForeignKey, OneToOneField, ManyToManyField, ManyToOneRel

from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from registrar import models
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

    def get(self, request, user_id):
        """current_user refers to the 'source' user where the button that redirects to this view was clicked.
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
        """This handles the transfer from selected_user to current_user then deletes selected_user."""
        current_user = get_object_or_404(User, pk=user_id)
        selected_user_id = request.POST.get("selected_user")
        selected_user = get_object_or_404(User, pk=selected_user_id)

        try:
            # Make this atomic so that we don't get any partial transfers
            with transaction.atomic():
                change_logs = []

                self._delete_duplicate_user_domain_roles_and_log(selected_user, current_user, change_logs)

                self._delete_duplicate_user_portfolio_permissions_and_log(selected_user, current_user, change_logs)
                # Dynamically handle related fields
                self.transfer_related_fields_and_log(selected_user, current_user, change_logs)

                # Success message if any related objects were updated
                logger.debug(f"change_logs: {change_logs}")
                if change_logs:
                    logger.debug(f"change_logs: {change_logs}")
                    success_message = f"Data transferred successfully for the following objects: {change_logs}"
                    messages.success(request, success_message)

                logger.debug("Deleting old user")
                selected_user.delete()
                messages.success(request, f"Deleted {selected_user} {selected_user.username}")

        except Exception as e:
            messages.error(request, f"An error occurred during the transfer: {e}")
            logger.error(f"An error occurred during the transfer: {e}", exc_info=True)

        return redirect("admin:registrar_user_change", object_id=user_id)

    def _delete_duplicate_user_portfolio_permissions_and_log(self, selected_user, current_user, change_logs):
        """
        Check and remove duplicate UserPortfolioPermission objects from the selected_user based on portfolios associated with the current_user.
        """
        try:
            # Fetch portfolios associated with the current_user
            current_user_portfolios = UserPortfolioPermission.objects.filter(user=current_user).values_list(
                "portfolio_id", flat=True
            )

            # Identify duplicates in selected_user for these portfolios
            duplicates = UserPortfolioPermission.objects.filter(
                user=selected_user, portfolio_id__in=current_user_portfolios
            )

            duplicate_count = duplicates.count()

            if duplicate_count > 0:
                # Log the specific duplicates before deletion for better traceability
                duplicate_permissions = list(duplicates)
                logger.debug(f"Duplicate permissions to be removed: {duplicate_permissions}")

                duplicates.delete()
                logger.info(
                    f"Removed {duplicate_count} duplicate UserPortfolioPermission(s) from user_id {selected_user.id} for portfolios already associated with user_id {current_user.id}"
                )
                change_logs.append(
                    f"Removed {duplicate_count} duplicate UserPortfolioPermission(s) from user_id {selected_user.id} for portfolios already associated with user_id {current_user.id}"
                )

        except Exception as e:
            logger.error(f"Failed to check and remove duplicate UserPortfolioPermissions: {e}", exc_info=True)
            raise

    def _delete_duplicate_user_domain_roles_and_log(self, selected_user, current_user, change_logs):
        """
        Check and remove duplicate UserDomainRole objects from the selected_user based on domains associated with the current_user.
        Retain one instance per domain to maintain data integrity.
        """

        try:
            # Fetch domains associated with the current_user
            current_user_domains = UserDomainRole.objects.filter(user=current_user).values_list("domain_id", flat=True)

            # Identify duplicates in selected_user for these domains
            duplicates = UserDomainRole.objects.filter(user=selected_user, domain_id__in=current_user_domains)

            duplicate_count = duplicates.count()

            if duplicate_count > 0:
                duplicates.delete()
                logger.info(
                    f"Removed {duplicate_count} duplicate UserDomainRole(s) from user_id {selected_user.id} "
                    f"for domains already associated with user_id {current_user.id}"
                )
                change_logs.append(
                    f"Removed {duplicate_count} duplicate UserDomainRole(s) from user_id {selected_user.id} "
                    f"for domains already associated with user_id {current_user.id}"
                )

        except Exception as e:
            logger.error(f"Failed to check and remove duplicate UserDomainRoles: {e}", exc_info=True)
            raise

    def transfer_related_fields_and_log(self, selected_user, current_user, change_logs):
        """
        Dynamically find all related fields to the User model and transfer them from selected_user to current_user.
        Handles ForeignKey, OneToOneField, ManyToManyField, and ManyToOneRel relationships.
        """
        user_model = User

        # Handle forward relationships
        for related_field in user_model._meta.get_fields():
            if related_field.is_relation and related_field.related_model:
                if isinstance(related_field, ForeignKey):
                    self._handle_foreign_key(related_field, selected_user, current_user, change_logs)
                elif isinstance(related_field, OneToOneField):
                    self._handle_one_to_one(related_field, selected_user, current_user, change_logs)
                elif isinstance(related_field, ManyToManyField):
                    self._handle_many_to_many(related_field, selected_user, current_user, change_logs)
                elif isinstance(related_field, ManyToOneRel):
                    self._handle_many_to_one_rel(related_field, selected_user, current_user, change_logs)

        # # Handle reverse relationships
        for related_object in user_model._meta.related_objects:
            if isinstance(related_object, ManyToOneRel):
                self._handle_many_to_one_rel(related_object, selected_user, current_user, change_logs)
            elif isinstance(related_object.field, OneToOneField):
                self._handle_one_to_one_reverse(related_object, selected_user, current_user, change_logs)
            elif isinstance(related_object.field, ForeignKey):
                self._handle_foreign_key_reverse(related_object, selected_user, current_user, change_logs)
            elif isinstance(related_object.field, ManyToManyField):
                self._handle_many_to_many_reverse(related_object, selected_user, current_user, change_logs)

    def _handle_foreign_key(self, related_field: ForeignKey, selected_user, current_user, change_logs):
        related_name = related_field.get_accessor_name()
        related_manager = getattr(selected_user, related_name, None)

        if related_manager.count() > 0:
            related_queryset = related_manager.all()
            for obj in related_queryset:
                setattr(obj, related_field.field.name, current_user)
                obj.save()
                self.log_change(selected_user, current_user, related_field.field.name, change_logs)

    def _handle_one_to_one(self, related_field: OneToOneField, selected_user, current_user, change_logs):
        related_name = related_field.get_accessor_name()
        related_object = getattr(selected_user, related_name, None)

        if related_object:
            setattr(related_object, related_field.field.name, current_user)
            related_object.save()
            self.log_change(selected_user, current_user, related_field.field.name, change_logs)

    def _handle_many_to_many(self, related_field: ManyToManyField, selected_user, current_user, change_logs):
        related_manager = getattr(selected_user, related_field.name, None)
        if related_manager.count() > 0:
            related_queryset = related_manager.all()
            getattr(current_user, related_field.name).add(*related_queryset)
            self.log_change(selected_user, current_user, related_field.name, change_logs)

    def _handle_many_to_one_rel(
        self, related_object: ManyToOneRel, selected_user: User, current_user: User, change_logs: List[str]
    ):
        related_model = related_object.related_model
        related_name = related_object.field.name

        related_queryset = related_model.objects.filter(**{related_name: selected_user})

        if related_queryset.count() > 0:
            for obj in related_queryset:
                setattr(obj, related_name, current_user)
                obj.save()
                self.log_change(selected_user, current_user, related_name, change_logs)

    def _handle_one_to_one_reverse(
        self, related_object: OneToOneField, selected_user: User, current_user: User, change_logs: List[str]
    ):
        related_model = related_object.related_model
        field_name = related_object.field.name

        try:
            related_instance = related_model.objects.filter(**{field_name: selected_user}).first()
            setattr(related_instance, field_name, current_user)
            related_instance.save()
            self.log_change(selected_user, current_user, field_name, change_logs)
        except related_model.DoesNotExist:
            logger.warning(f"No related instance found for reverse OneToOneField {field_name} for {selected_user}")

    def _handle_foreign_key_reverse(
        self, related_object: ForeignKey, selected_user: User, current_user: User, change_logs: List[str]
    ):
        related_model = related_object.related_model
        field_name = related_object.field.name

        related_queryset = related_model.objects.filter(**{field_name: selected_user})

        if related_queryset.count() > 0:
            for obj in related_queryset:
                setattr(obj, field_name, current_user)
                obj.save()
                self.log_change(selected_user, current_user, field_name, change_logs)

    def _handle_many_to_many_reverse(
        self, related_object: ManyToManyField, selected_user: User, current_user: User, change_logs: List[str]
    ):
        related_model = related_object.related_model
        field_name = related_object.field.name

        related_queryset = related_model.objects.filter(**{field_name: selected_user})
        if related_queryset.count() > 0:
            getattr(current_user, field_name).add(*related_queryset)
            self.log_change(selected_user, current_user, field_name, change_logs)

    @classmethod
    def log_change(cls, selected_user, current_user, field_name, change_logs):
        log_entry = f"Transferred {field_name} from {selected_user} to {current_user}"
        logger.info(log_entry)
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
