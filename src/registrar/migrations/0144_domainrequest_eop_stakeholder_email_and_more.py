# Generated by Django 4.2.17 on 2025-03-17 20:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("registrar", "143_create_groups_v18"),
    ]

    operations = [
        migrations.AddField(
            model_name="domainrequest",
            name="eop_stakeholder_email",
            field=models.EmailField(blank=True, max_length=254, null=True, verbose_name="EOP Stakeholder Email"),
        ),
        migrations.AddField(
            model_name="domainrequest",
            name="eop_stakeholder_first_name",
            field=models.CharField(blank=True, null=True, verbose_name="EOP Stakeholder First Name"),
        ),
        migrations.AddField(
            model_name="domainrequest",
            name="eop_stakeholder_last_name",
            field=models.CharField(blank=True, null=True, verbose_name="EOP Stakeholder Last Name"),
        ),
        migrations.AddField(
            model_name="domainrequest",
            name="working_with_eop",
            field=models.BooleanField(blank=True, null=True),
        ),
    ]
