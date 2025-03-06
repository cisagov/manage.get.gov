# Generated by Django 4.2.17 on 2025-03-05 15:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("registrar", "0142_domainrequest_feb_purpose_choice_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="domainrequest",
            name="eop_contact",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="eop_contact",
                to="registrar.contact",
            ),
        ),
        migrations.AddField(
            model_name="domainrequest",
            name="working_with_eop",
            field=models.BooleanField(blank=True, null=True),
        ),
    ]
