from django.db import models


class BranchChoices(models.TextChoices):
    EXECUTIVE = "executive", "Executive"
    JUDICIAL = "judicial", "Judicial"
    LEGISLATIVE = "legislative", "Legislative"
