# Generated by Django 4.2.7 on 2023-12-05 10:00

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("registrar", "0048_alter_transitiondomain_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="domainapplication",
            name="current_websites",
            field=models.ManyToManyField(
                blank=True, related_name="current+", to="registrar.website", verbose_name="websites"
            ),
        ),
        migrations.AlterField(
            model_name="domainapplication",
            name="other_contacts",
            field=models.ManyToManyField(
                blank=True, related_name="contact_applications", to="registrar.contact", verbose_name="contacts"
            ),
        ),
        migrations.AlterField(
            model_name="domaininformation",
            name="other_contacts",
            field=models.ManyToManyField(
                blank=True,
                related_name="contact_applications_information",
                to="registrar.contact",
                verbose_name="contacts",
            ),
        ),
    ]
