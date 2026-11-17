# Renames the "requestor_not_eligible" rejection reason to "requestor_not_authorized".

from django.db import migrations, models

OLD_VALUE = "requestor_not_eligible"
NEW_VALUE = "requestor_not_authorized"


def forwards(apps, schema_editor):
    DomainRequest = apps.get_model("registrar", "DomainRequest")
    DomainRequest.objects.filter(rejection_reason=OLD_VALUE).update(rejection_reason=NEW_VALUE)


def backwards(apps, schema_editor):
    DomainRequest = apps.get_model("registrar", "DomainRequest")
    DomainRequest.objects.filter(rejection_reason=NEW_VALUE).update(rejection_reason=OLD_VALUE)


class Migration(migrations.Migration):

    dependencies = [
        ("registrar", "0201_rename_generic_org_type_domaininformation_organization_type_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="domainrequest",
            name="rejection_reason",
            field=models.TextField(
                blank=True,
                choices=[
                    ("domain_purpose", "Purpose requirements not met"),
                    ("requestor_not_authorized", "Requestor not authorized to make request"),
                    ("org_has_domain", "Org already has a .gov domain"),
                    ("contacts_not_verified", "Org contacts couldn't be verified"),
                    ("org_not_eligible", "Org not eligible for a .gov domain"),
                    ("naming_requirements", "Naming requirements not met"),
                    ("other", "Other/Unspecified"),
                ],
                null=True,
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
