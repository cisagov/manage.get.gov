# Generated by Django 4.2.7 on 2024-01-08 23:24

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("registrar", "0060_domain_deleted_domain_first_ready"),
    ]

    operations = [
        migrations.AlterField(
            model_name="host",
            name="name",
            field=models.CharField(default=None, help_text="Fully qualified domain name", max_length=253),
        ),
    ]
