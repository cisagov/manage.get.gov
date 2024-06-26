# Generated by Django 4.2.10 on 2024-06-12 14:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("registrar", "0099_federalagency_federal_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="domainrequest",
            name="action_needed_reason",
            field=models.TextField(
                blank=True,
                choices=[
                    ("eligibility_unclear", "Unclear organization eligibility"),
                    ("questionable_authorizing_official", "Questionable authorizing official"),
                    ("already_has_domains", "Already has domains"),
                    ("bad_name", "Doesn’t meet naming requirements"),
                    ("other", "Other (no auto-email sent)"),
                ],
                null=True,
            ),
        ),
    ]
