# coding: utf-8
from __future__ import unicode_literals

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.utils import timezone

logger = logging.getLogger(__name__)


class OpenIdConnectBackend(ModelBackend):
    """
    This backend checks a previously performed OIDC authentication.
    If it is OK and the user already exists in the database, it is returned.
    If it is OK and user does not exist in the database, it is created and
        returned unless setting OIDC_CREATE_UNKNOWN_USER is False.
    In all other cases, None is returned.
    """

    def authenticate(self, request, **kwargs):
        logger.debug("kwargs %s" % kwargs)
        user = None
        if not kwargs or "sub" not in kwargs.keys():
            return user

        UserModel = get_user_model()
        username = self.clean_username(kwargs["sub"])

        # Some OP may actually choose to withhold some information, so we must
        # test if it is present
        openid_data = {"last_login": timezone.now()}
        openid_data["first_name"] = kwargs.get("given_name", "")
        openid_data["last_name"] = kwargs.get("family_name", "")
        openid_data["email"] = kwargs.get("email", "")
        openid_data["phone"] = kwargs.get("phone", "")

        # Note that this could be accomplished in one try-except clause, but
        # instead we use get_or_create when creating unknown users since it has
        # built-in safeguards for multiple threads.
        if getattr(settings, "OIDC_CREATE_UNKNOWN_USER", True):
            args = {
                UserModel.USERNAME_FIELD: username,
                # defaults _will_ be updated, these are not fallbacks
                "defaults": openid_data,
            }

            user, created = UserModel.objects.get_or_create(**args)

            if not created:
                # If user exists, update existing user
                self.update_existing_user(user, args["defaults"])
            else:
                # If user is created, configure the user
                user = self.configure_user(user, **kwargs)
        else:
            try:
                user = UserModel.objects.get_by_natural_key(username)
            except UserModel.DoesNotExist:
                return None
        # run this callback for a each login
        user.on_each_login()
        return user

    def update_existing_user(self, user, kwargs):
        """
        Update user fields without overwriting certain fields.

        Args:
            user: User object to be updated.
            kwargs: Dictionary containing fields to update and their new values.

        Note:
            This method updates user fields while preserving the values of 'first_name',
            'last_name', and 'phone' fields, unless specific conditions are met.

            - 'first_name', 'last_name' or 'phone' will be updated if the provided value is not empty.
        """

        fields_to_check = ["first_name", "last_name", "phone"]

        # Iterate over fields to update
        for key, value in kwargs.items():
            # Check if the field is not 'first_name', 'last_name', or 'phone',
            # or if it's 'first_name' or 'last_name' or 'phone' and the provided value is not empty
            if key not in fields_to_check or (key in fields_to_check and value):
                # Update the corresponding attribute of the user object
                setattr(user, key, value)

        # Save the user object with the updated fields
        user.save()

    def clean_username(self, username):
        """
        Performs any cleaning on the "username" prior to using it to get or
        create the user object.  Returns the cleaned username.
        """
        return username

    def configure_user(self, user, **kwargs):
        """
        Configures a user after creation and returns the updated user.
        """
        user.set_unusable_password()
        return user
