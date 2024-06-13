from django.db import models


class BranchChoices(models.TextChoices):
    EXECUTIVE = "executive", "Executive"
    JUDICIAL = "judicial", "Judicial"
    LEGISLATIVE = "legislative", "Legislative"

    @classmethod
    def get_branch_label(cls, branch_name: str):
        """Returns the associated label for a given org name"""
        return cls(branch_name).label if branch_name else None
