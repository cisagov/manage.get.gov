# Generated by Django 4.2.20 on 2025-04-14 13:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("registrar", "0145_create_groups_v19"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="domainrequest",
            name="eop_stakeholder_email",
        ),
        migrations.AlterField(
            model_name="domainrequest",
            name="feb_naming_requirements",
            field=models.BooleanField(blank=True, null=True, verbose_name="Meets naming requirements"),
        ),
        migrations.AlterField(
            model_name="domainrequest",
            name="feb_naming_requirements_details",
            field=models.TextField(
                blank=True,
                help_text="Required if requested domain that doesn't meet naming requirements",
                null=True,
                verbose_name="Domain name rationale",
            ),
        ),
        migrations.AlterField(
            model_name="domainrequest",
            name="feb_purpose_choice",
            field=models.CharField(
                blank=True,
                choices=[
                    ("new", "Used for a new website"),
                    ("redirect", "Used as a redirect for an existing website"),
                    ("other", "Not for a website"),
                ],
                null=True,
                verbose_name="Purpose type",
            ),
        ),
        migrations.AlterField(
            model_name="domainrequest",
            name="interagency_initiative_details",
            field=models.TextField(blank=True, null=True, verbose_name="Interagency initiative"),
        ),
        migrations.AlterField(
            model_name="domainrequest",
            name="time_frame_details",
            field=models.TextField(blank=True, null=True, verbose_name="Target time frame"),
        ),
    ]
