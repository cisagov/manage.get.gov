# Generated by Django 4.2.10 on 2024-10-08 18:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("registrar", "0132_alter_domaininformation_portfolio_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="domainrequest",
            name="rejection_reason_email",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="domainrequest",
            name="rejection_reason",
            field=models.TextField(
                blank=True,
                choices=[
                    ("domain_purpose", "Purpose requirements not met"),
                    ("requestor_not_eligible", "Requestor not eligible to make request"),
                    ("org_has_domain", "Org already has a .gov domain"),
                    ("contacts_not_verified", "Org contacts couldn't be verified"),
                    ("org_not_eligible", "Org not eligible for a .gov domain"),
                    ("naming_requirements", "Naming requirements not met"),
                    ("other", "Other/Unspecified"),
                ],
                null=True,
            ),
        ),
    ]