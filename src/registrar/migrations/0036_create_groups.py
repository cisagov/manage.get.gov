# This migration creates the create_full_access_group and create_cisa_analyst_group groups
# It is dependent on 0035 (which populates ContentType and Permissions)
# If permissions on the groups need changing, edit CISA_ANALYST_GROUP_PERMISSIONS
# in the user_group model then:
# step 1: docker-compose exec app ./manage.py migrate --fake registrar 0035_contenttypes_permissions
# step 2: docker-compose exec app ./manage.py migrate registrar 0036_create_groups
# step 3: fake run the latest migration in the migrations list
# Alternatively:
# Only step: duplicate the migtation that loads data and run: docker-compose exec app ./manage.py migrate

from django.db import migrations
from registrar.models import UserGroup

def create_groups():
    UserGroup.create_cisa_analyst_group()
    UserGroup.create_full_access_group()


class Migration(migrations.Migration):
    dependencies = [
        ("registrar", "0035_contenttypes_permissions"),
    ]

    operations = [
        migrations.RunPython(
            create_groups,  # noqa
            reverse_code=migrations.RunPython.noop,
            atomic=True,
        ),
    ]
