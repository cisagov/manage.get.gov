# Generated by Django 4.2.10 on 2024-03-15 18:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("registrar", "0076_alter_domainrequest_current_websites_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="publiccontact",
            name="fax",
            field=models.CharField(
                blank=True, help_text="Contact's fax number (null ok). Must be in ITU.E164.2005 format.", null=True
            ),
        ),
        migrations.AlterField(
            model_name="publiccontact",
            name="org",
            field=models.CharField(blank=True, help_text="Contact's organization (null ok)", null=True),
        ),
        migrations.AlterField(
            model_name="publiccontact",
            name="street2",
            field=models.CharField(blank=True, help_text="Contact's street (null ok)", null=True),
        ),
        migrations.AlterField(
            model_name="publiccontact",
            name="street3",
            field=models.CharField(blank=True, help_text="Contact's street (null ok)", null=True),
        ),
    ]
