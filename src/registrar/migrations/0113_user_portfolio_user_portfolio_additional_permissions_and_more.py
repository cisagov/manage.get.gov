# Generated by Django 4.2.10 on 2024-07-22 19:19

from django.conf import settings
import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("registrar", "0112_remove_contact_registrar_c_user_id_4059c4_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="portfolio",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="user",
                to="registrar.portfolio",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="portfolio_additional_permissions",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(
                    choices=[
                        ("view_all_domains", "View all domains and domain reports"),
                        ("view_managed_domains", "View managed domains"),
                        ("edit_domains", "User is a manager on a domain"),
                        ("view_member", "View members"),
                        ("edit_member", "Create and edit members"),
                        ("view_all_requests", "View all requests"),
                        ("view_created_requests", "View created requests"),
                        ("edit_requests", "Create and edit requests"),
                        ("view_portfolio", "View organization"),
                        ("edit_portfolio", "Edit organization"),
                    ],
                    max_length=50,
                ),
                blank=True,
                help_text="Select one or more additional permissions.",
                null=True,
                size=None,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="portfolio_roles",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(
                    choices=[
                        ("organization_admin", "Admin"),
                        ("organization_admin_read_only", "Admin read only"),
                        ("organization_member", "Member"),
                    ],
                    max_length=50,
                ),
                blank=True,
                help_text="Select one or more roles.",
                null=True,
                size=None,
            ),
        ),
        migrations.AlterField(
            model_name="portfolio",
            name="creator",
            field=models.ForeignKey(
                help_text="Associated user",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="creator",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
