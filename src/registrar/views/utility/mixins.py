"""Mixin classes."""

import logging

logger = logging.getLogger(__name__)


class OrderableFieldsMixin:
    """
    Mixin to add multi-field ordering capabilities to a Django ModelAdmin on admin_order_field.
    """

    custom_sort_name_prefix = "get_sortable_"
    orderable_fk_fields = []  # type: ignore

    def __new__(cls, *args, **kwargs):
        """
        This magic method is called when a new instance of the class (or subclass) is created.
        It dynamically adds a new method to the class for each field in `orderable_fk_fields`.
        Then, it will update the `list_display` attribute such that it uses these generated methods.
        """
        new_class = super().__new__(cls)

        # If the class doesn't define anything for orderable_fk_fields, then we should
        # just skip this additional logic
        if not hasattr(cls, "orderable_fk_fields") or len(cls.orderable_fk_fields) == 0:
            return new_class

        # Check if the list_display attribute exists, and if it does, create a local copy of that list.
        list_display_exists = hasattr(cls, "list_display") and isinstance(cls.list_display, list)
        new_list_display = cls.list_display.copy() if list_display_exists else []

        for field, sort_field in cls.orderable_fk_fields:
            updated_name = cls.custom_sort_name_prefix + field

            # For each item in orderable_fk_fields, create a function and associate it with admin_order_field.
            setattr(new_class, updated_name, cls._create_orderable_field_method(field, sort_field))

            # Update the list_display variable to use our newly created functions
            if list_display_exists and field in cls.list_display:
                index = new_list_display.index(field)
                new_list_display[index] = updated_name
            elif list_display_exists:
                new_list_display.append(updated_name)

        # Replace the old list with the updated one
        if list_display_exists:
            cls.list_display = new_list_display

        return new_class

    @classmethod
    def _create_orderable_field_method(cls, field, sort_field):
        """
        This class method is a factory for creating dynamic methods that will be attached
        to the ModelAdmin subclass.
        It is used to customize how fk fields are ordered.

        In essence, this function will more or less generate code that looks like this,
        for a given tuple defined in orderable_fk_fields:

        ```
        def get_sortable_requested_domain(self, obj):
            return obj.requested_domain
        # Allows column order sorting
        get_sortable_requested_domain.admin_order_field = "requested_domain__name"
        # Sets column's header name
        get_sortable_requested_domain.short_description = "requested domain"
        ```

        Or for fields with multiple order_fields:

        ```
        def get_sortable_requester(self, obj):
            return obj.requester
        # Allows column order sorting
        get_sortable_requester.admin_order_field = ["requester__first_name", "requester__last_name"]
        # Sets column's header
        get_sortable_requester.short_description = "requester"
        ```

        Parameters:
        cls: The class that this method is being called on. In the context of this mixin,
        it would be the ModelAdmin subclass.
        field: A string representing the name of the attribute that
        the dynamic method will fetch from the model instance.
        sort_field: A string or list of strings representing the
        field(s) to sort by (ex: "name" or "requester")

        Returns:
        method: The dynamically created method.

        The dynamically created method has the following attributes:
        __name__: A string representing the name of the method. This is set to "get_{field}".
        admin_order_field: A string or list of strings representing the field(s) that
        Django should sort by when the column is clicked in the admin interface.
        short_description: A string used as the column header in the admin interface.
        Will replace underscores with spaces.
        """

        def method(obj):
            """
            Template method for patterning.

            Returns (example):
            ```
            def get_requester(self, obj):
                return obj.requester
            ```
            """
            attr = getattr(obj, field)
            return attr

        # Set the function name. For instance, if the field is "domain",
        # then this will generate a function called "get_sort_domain".
        # This is done rather than just setting the name to the attribute to avoid
        # naming conflicts.
        method.__name__ = cls.custom_sort_name_prefix + field

        # Check if a list is passed in, or just a string.
        if isinstance(sort_field, list):
            sort_list = []
            for sort_field_item in sort_field:
                order_field_string = f"{field}__{sort_field_item}"
                sort_list.append(order_field_string)
            # If its a list, return an array of fields to sort on.
            # For instance, ["requester__first_name", "requester__last_name"]
            method.admin_order_field = sort_list
        else:
            # If its not a list, just return a string
            method.admin_order_field = f"{field}__{sort_field}"

        # Infer the column name in a similar manner to how Django does
        method.short_description = field.replace("_", " ")
        return method
