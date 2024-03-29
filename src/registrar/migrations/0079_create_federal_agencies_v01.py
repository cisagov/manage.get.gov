# Generated by Django 4.2.10 on 2024-03-22 22:18

from django.db import migrations, models
from registrar.models import FederalAgency
from typing import Any


# For linting: RunPython expects a function reference.
def create_federal_agencies(apps, schema_editor) -> Any:
    FederalAgency.create_federal_agencies(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("registrar", "0078_rename_organization_type_domaininformation_generic_org_type_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="FederalAgency",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("agency", models.CharField(blank=True, help_text="Federal agency", null=True)),
            ],
            options={
                "verbose_name": "Federal agency",
                "verbose_name_plural": "Federal agencies",
            },
        ),
        migrations.RunPython(
            create_federal_agencies,
            reverse_code=migrations.RunPython.noop,
            atomic=True,
        ),
    ]
