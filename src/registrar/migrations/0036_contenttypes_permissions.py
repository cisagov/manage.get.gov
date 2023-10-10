# From mithuntnt's answer on:
# https://stackoverflow.com/questions/26464838/getting-model-contenttype-in-migration-django-1-7
# The problem is that ContentType and Permission objects are not already created
# while we're still running migrations, so we'll go ahead and speed up that process
# a bit before we attempt to create groups which require Permissions and ContentType.

from django.conf import settings
from django.db import migrations


def create_all_contenttypes(**kwargs):
    from django.apps import apps
    from django.contrib.contenttypes.management import create_contenttypes

    for app_config in apps.get_app_configs():
        create_contenttypes(app_config, **kwargs)


def create_all_permissions(**kwargs):
    from django.contrib.auth.management import create_permissions
    from django.apps import apps

    for app_config in apps.get_app_configs():
        create_permissions(app_config, **kwargs)


def forward(apps, schema_editor):
    create_all_contenttypes()
    create_all_permissions()


def backward(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contenttypes", "0002_remove_content_type_name"),
        ("registrar", "0035_alter_user_options"),
    ]

    operations = [migrations.RunPython(forward, backward)]
