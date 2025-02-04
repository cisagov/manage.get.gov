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
        logger.debug("kwargs %s", kwargs)

        if not kwargs or "sub" not in kwargs:
            return None

        UserModel = get_user_model()
        username = self.clean_username(kwargs["sub"])
        openid_data = self.extract_openid_data(kwargs)

        if getattr(settings, "OIDC_CREATE_UNKNOWN_USER", True):
            user = self.get_or_create_user(UserModel, username, openid_data, kwargs)
        else:
            user = self.get_user_by_username(UserModel, username)

        if user:
            user.on_each_login()

        return user

    def extract_openid_data(self, kwargs):
        """Extract OpenID data from authentication kwargs."""
        return {
            "last_login": timezone.now(),
            "first_name": kwargs.get("given_name", ""),
            "last_name": kwargs.get("family_name", ""),
            "email": kwargs.get("email", ""),
            "phone": kwargs.get("phone", ""),
        }

    def get_or_create_user(self, UserModel, username, openid_data, kwargs):
        """Retrieve user by username or email, or create a new user."""
        user = self.get_user_by_username(UserModel, username)

        if not user and openid_data["email"]:
            user = self.get_user_by_email(UserModel, openid_data["email"])
            if user:
                # if found by email, update the username
                setattr(user, UserModel.USERNAME_FIELD, username)

        if not user:
            user = UserModel.objects.create(**{UserModel.USERNAME_FIELD: username}, **openid_data)
            return self.configure_user(user, **kwargs)

        self.update_existing_user(user, openid_data)
        return user

    def get_user_by_username(self, UserModel, username):
        """Retrieve user by username."""
        try:
            return UserModel.objects.get(**{UserModel.USERNAME_FIELD: username})
        except UserModel.DoesNotExist:
            return None

    def get_user_by_email(self, UserModel, email):
        """Retrieve user by email."""
        try:
            return UserModel.objects.get(email=email)
        except UserModel.DoesNotExist:
            return None

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
