# Generated by Django 4.2.10 on 2024-08-15 15:32

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("registrar", "0117_alter_portfolioinvitation_portfolio_additional_permissions_and_more"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="portfolio",
            options={"ordering": ["organization_name"]},
        ),
        migrations.AlterField(
            model_name="portfolio",
            name="creator",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="created_portfolios",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Portfolio creator",
            ),
        ),
        migrations.AlterField(
            model_name="portfolio",
            name="organization_name",
            field=models.CharField(blank=True, null=True, verbose_name="Portfolio organization"),
        ),
        migrations.AlterField(
            model_name="portfolio",
            name="senior_official",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="registrar.seniorofficial"
            ),
        ),
        migrations.AlterField(
            model_name="suborganization",
            name="portfolio",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="portfolio_suborganizations",
                to="registrar.portfolio",
            ),
        ),
    ]
