"""This file contains general purpose helpers that don't belong in any specific location"""

import time
import logging
from urllib.parse import urlparse, urlunparse, urlencode
from django.urls import resolve, Resolver404

logger = logging.getLogger(__name__)


class Timer:
    """
    This class is used to measure execution time for performance profiling.
    __enter__ and __exit__ is used such that you can wrap any code you want
    around a with statement. After this exits, logger.info will print
    the execution time in seconds.

    Note that this class does not account for general randomness as more
    robust libraries do, so there is some tiny amount of latency involved
    in using this, but it is minimal enough that for most applications it is not
    noticable.

    Usage:
    with Timer():
        ...some code
    """

    def __enter__(self):
        """Starts the timer"""
        self.start = time.time()
        # This allows usage of the instance within the with block
        return self

    def __exit__(self, *args):
        """Ends the timer and logs what happened"""
        self.end = time.time()
        self.duration = self.end - self.start
        logger.info(f"Execution time: {self.duration} seconds")

# TODO: Remove the entire helper function (Ticket #5493)
class CreateOrUpdateOrganizationTypeHelper:
    """Synchronize organization_type with generic_org_type for domain records."""

    def __init__(self, sender, instance):
        self.sender = sender
        self.instance = instance

    def create_or_update_organization_type(self, force_update=False):
        """Synchronize changed value, or fill a missing value when force_update."""

        # A new record is added with organization_type not defined.
        # This happens from the regular domain request flow.
        is_new_instance = self.instance.id is None
        if is_new_instance:
            self._handle_new_instance()
        else:
            self._handle_existing_instance(force_update)

        return self.instance

    def _handle_new_instance(self):
        # == Check for invalid conditions before proceeding == #
        should_proceed = self._validate_new_instance()
        if not should_proceed:
            return None
        # == Program flow will halt here if there is no reason to update == #

        # == Update the linked values == #
        organization_type_needs_update = self.instance.organization_type is None
        generic_org_type_needs_update = self.instance.generic_org_type is None

        # Update the field
        self._update_fields(organization_type_needs_update, generic_org_type_needs_update)

    def _handle_existing_instance(self, force_update_when_no_changes_are_found=False):
        # == Init variables == #
        try:
            # Instance is already in the database, fetch its current state
            current_instance = self.sender.objects.get(id=self.instance.id)

            # Check the new and old values
            generic_org_type_changed = self.instance.generic_org_type != current_instance.generic_org_type
            organization_type_changed = self.instance.organization_type != current_instance.organization_type

            # == Check for invalid conditions before proceeding == #
            if organization_type_changed and generic_org_type_changed:
                # Since organization type is linked with generic_org_type,
                # we have to update one or the other, not both.
                # This will not happen in normal flow as it is not possible otherwise.
                raise ValueError("Cannot update organization_type and generic_org_type simultaneously.")
            elif not organization_type_changed and not generic_org_type_changed:
                # No changes found
                if force_update_when_no_changes_are_found:
                    # If we want to force an update anyway, we can treat this record like
                    # its a new one in that we check for "None" values rather than changes.
                    self._handle_new_instance()
            else:
                # == Update the linked values == #
                # Find out which field needs updating
                organization_type_needs_update = generic_org_type_changed
                generic_org_type_needs_update = organization_type_changed

                # Update the field
                self._update_fields(organization_type_needs_update, generic_org_type_needs_update)
        except self.sender.DoesNotExist:
            # this exception should only be raised when import_export utility attempts to import
            # a new row and already has an id
            pass

    def _update_fields(self, organization_type_needs_update, generic_org_type_needs_update):
        """
        Validates the conditions for updating organization and generic organization types.

        Raises:
            ValueError: If both organization_type_needs_update and generic_org_type_needs_update are True,
                        indicating an attempt to update both fields simultaneously, which is not allowed.
        """
        # We shouldn't update both of these at the same time.
        # It is more useful to have these as seperate variables, but it does impose
        # this restraint.
        if organization_type_needs_update and generic_org_type_needs_update:
            raise ValueError("Cannot update both org type and generic org type at the same time.")

        if organization_type_needs_update:
            self._update_org_type_from_generic_org()
        elif generic_org_type_needs_update:
            self._update_generic_org_from_org_type()

    def _update_org_type_from_generic_org(self):
        self.instance.organization_type = (
                str(self.instance.generic_org_type) if self.instance.generic_org_type is not None else None
            )

    def _update_generic_org_from_org_type(self):
        self.instance.generic_org_type = (
                str(self.instance.organization_type) if self.instance.organization_type is not None else None
            )

    def _validate_new_instance(self) -> bool:
        """
        Validates whether a new instance of DomainRequest or DomainInformation can proceed with the update
        based on the consistency between organization_type and generic_org_type.

        Returns a boolean determining if execution should proceed or not.

        Raises:
            ValueError if there is a mismatch between organization_type and generic_org_type
        """

        # We conditionally accept both of these values to exist simultaneously, as long as
        # those values do not intefere with eachother.
        # Because this condition can only be triggered through a dev (no user flow),
        # we throw an error if an invalid state is found here.
        if self.instance.organization_type and self.instance.generic_org_type:
            if str(self.instance.generic_org_type) != str(self.instance.organization_type):
                message = "organization_type and generic_org_type must match when both are provided."
                logger.error("_validate_new_instance: %s", message)
                raise ValueError(message)

            return True
        elif not self.instance.organization_type and not self.instance.generic_org_type:
            return False
        else:
            return True


def replace_url_queryparams(url_to_modify: str, query_params, convert_list_to_csv=False):
    """
    Replaces the query parameters of a given URL.
    Because this replaces them, this can be used to either add, delete, or modify.
    Args:
        url_to_modify (str): The URL whose query parameters need to be modified.
        query_params (dict): Dictionary of query parameters to use.
        convert_list_to_csv (bool): If the queryparam contains a list of items,
        convert it to a csv representation instead.
    Returns:
        str: The modified URL with the updated query parameters.
    """

    # Ensure each key in query_params maps to a single value, not a list
    if convert_list_to_csv:
        for key, value in query_params.items():
            if isinstance(value, list):
                query_params[key] = ",".join(value)

    # Split the URL into parts
    url_parts = list(urlparse(url_to_modify))

    # Modify the query param bit
    url_parts[4] = urlencode(query_params)

    # Reassemble the URL
    new_url = urlunparse(url_parts)

    return new_url


def convert_queryset_to_dict(queryset, is_model=True, key="id"):
    """
    Transforms a queryset into a dictionary keyed by a specified key (like "id").

    Parameters:
        requests (QuerySet or list of dicts): Input data.
        is_model (bool): Indicates if each item in 'queryset' are model instances (True) or dictionaries (False).
        key (str): Key or attribute to use for the resulting dictionary's keys.

    Returns:
        dict: Dictionary with keys derived from 'key' and values corresponding to items in 'queryset'.
    """

    if is_model:
        request_dict = {getattr(value, key): value for value in queryset}
    else:
        # Querysets sometimes contain sets of dictionaries.
        # Calling .values is an example of this.
        request_dict = {value[key]: value for value in queryset}

    return request_dict


def get_url_name(path):
    """
    Given a URL path, returns the corresponding URL name defined in urls.py.

    Args:
        path (str): The URL path to resolve.

    Returns:
        str or None: The URL name if it exists, otherwise None.
    """
    try:
        match = resolve(path)
        return match.url_name
    except Resolver404:
        try:
            logger.info(f"Path {path} not resolved. Rechecking with a trailing slash")
            match = resolve(path + "/")
            return match.url_name
        except Resolver404:
            logger.error(f"No matching URL name found for path: {path}")
            return None


def value_of_attribute(obj, attribute_name: str):
    """Returns the value of getattr if the attribute isn't callable.
    If it is, execute the underlying function and return that result instead."""
    value = getattr(obj, attribute_name)
    if callable(value):
        value = value()
    return value


def normalize_string(string_to_normalize, lowercase=True):
    """Normalizes a given string. Returns a string without extra spaces, in all lowercase."""
    if not isinstance(string_to_normalize, str):
        logger.error(f"normalize_string => {string_to_normalize} is not type str.")
        return string_to_normalize

    new_string = " ".join(string_to_normalize.split())
    return new_string.lower() if lowercase else new_string


def count_capitals(text: str, leading_only: bool):
    """Counts capital letters in a string.
    Args:
        text (str): The string to analyze.
        leading_only (bool): If False, counts all capital letters.
                                If True, only counts capitals at the start of words.
    Returns:
        int: Number of capital letters found.
    """
    if leading_only:
        return sum(word[0].isupper() for word in text.split() if word)
    return sum(c.isupper() for c in text if c)
