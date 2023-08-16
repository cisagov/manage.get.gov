import logging
from typing import Dict
from django.forms import ModelChoiceField

logger = logging.getLogger(__name__)


class SortingDictInterface:
    _model_list: Dict[type, type] = {}
    _sort_list: list[type] = []
    sorting_dict: Dict[type, type] = {}

    # _model_list and _sort_list can be
    # any length, and will be called multiple times.
    # We want the perf advantage of a dictionary,
    # while making creating new SortingDictInterface
    # items pretty straight forward and easy (aka as a list)
    def convert_list_to_dict(self, value_list):
        dictionary: Dict[type, type] = {}
        for item in value_list:
            dictionary[item] = item
        return dictionary

    def __init__(self, model_list, sort_list):
        self.sorting_dict = {
            "dropDownSelected": self.convert_list_to_dict(model_list),
            "sortBy": sort_list
        }


class AdminFormOrderHelper():
    """A helper class to order a dropdown field in Django Admin,
    takes the fields you want to order by as an array"""

    # Used to keep track of how we want to order_by certain FKs
    _sorting_dict: list[SortingDictInterface] = []

    def __init__(self, sort):
        self._sorting_dict = sort

    def get_ordered_form_field(self, form_field, db_field) -> (ModelChoiceField | None):
        """Orders the queryset for a ModelChoiceField
        based on the order_by_dict dictionary"""
        _order_by_list = []

        for item in self._sorting_dict:
            drop_down_selected = item["dropDownSelected"]
            sort_by = item["sortBy"]

            if db_field.name in drop_down_selected:
                _order_by_list = sort_by
                break

        # Only order if we choose to do so
        if _order_by_list is not None:
            form_field.queryset = form_field.queryset.order_by(*_order_by_list)

        return form_field
