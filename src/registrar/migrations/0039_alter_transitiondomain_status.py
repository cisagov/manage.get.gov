from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("registrar", "0038_create_groups_v02"),
    ]

    operations = [
        migrations.AlterField(
            model_name="transitiondomain",
            name="status",
            field=models.CharField(
                blank=True,
                choices=[("ready", "Ready"), ("on hold", "On Hold")],
                default="ready",
                help_text="domain status during the transfer",
                max_length=255,
                verbose_name="Status",
            ),
        ),
    ]
