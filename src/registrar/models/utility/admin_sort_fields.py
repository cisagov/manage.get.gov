from registrar.models.utility.admin_form_order_helper import (
    AdminFormOrderHelper,
    SortingDict,
)


class AdminSortFields:
    # Used to keep track of how we want to order_by certain FKs
    foreignkey_orderby_dict: list[SortingDict] = [
        # foreign_key - order_by
        # Handles fields that are sorted by 'first_name / last_name
        SortingDict(
            ["submitter", "authorizing_official", "investigator", "creator", "user"],
            ["first_name", "last_name"],
        ),
        # Handles fields that are sorted by 'name'
        SortingDict(["domain", "requested_domain"], ["name"]),
        SortingDict(["domain_application"], ["requested_domain__name"]),
    ]

    # For readability purposes, but can be replaced with a one liner
    def form_field_order_helper(self, form_field, db_field):
        """A shorthand for AdminFormOrderHelper(foreignkey_orderby_dict)
        .get_ordered_form_field(form_field, db_field)"""

        form = AdminFormOrderHelper(self.foreignkey_orderby_dict)
        return form.get_ordered_form_field(form_field, db_field)
