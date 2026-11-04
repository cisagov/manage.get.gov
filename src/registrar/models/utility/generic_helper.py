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
