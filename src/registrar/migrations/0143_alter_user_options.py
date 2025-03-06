# Generated by Django 4.2.17 on 2025-03-06 20:00

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("registrar", "0142_create_groups_v18"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="user",
            options={
                "permissions": [
                    ("analyst_access_permission", "Analyst Access Permission"),
                    ("omb_analyst_access_permission", "OMB Analyst Access Permission"),
                    ("full_access_permission", "Full Access Permission"),
                ]
            },
        ),
    ]
