from django.db.models import F, OuterRef, Exists
from django.apps import apps


class TribeHelper:
    """Shared helper functions for State Tribe and Federal Tribe"""

    @staticmethod
    def get_dropdown_options(model, name_field, portfolio_field):
        """
        Returns dropdown options flagged with whether a Portfolio exists for each tribe

        Params:
        model (type[Model]): the tribe model class (StateTribe or FederalTribe)
        name_field (str): that model's name field ("tribe_name" or "tribe_full_name")
        portfolio_field (str): the FK on Portfolio pointing at it ("state_tribe" or "federal_tribe")

        Returns (list[dict]): [{"id": int, "name": str, "has_existing_portfolio": bool}, ...]
        """
        Portfolio = apps.get_model("registrar", "Portfolio")

        existing = Portfolio.objects.filter(**{portfolio_field: OuterRef("pk")})

        return list(
            model.objects.annotate(
                name=F(name_field),
                has_existing_portfolio=Exists(existing),
            )
            .values("id", "name", "has_existing_portfolio")
            .order_by("name")
        )
