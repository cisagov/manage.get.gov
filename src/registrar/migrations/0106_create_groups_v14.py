# This migration creates the create_full_access_group and create_cisa_analyst_group groups
# It is dependent on 0079 (which populates federal agencies)
# If permissions on the groups need changing, edit CISA_ANALYST_GROUP_PERMISSIONS
# in the user_group model then:
# [NOT RECOMMENDED]
# step 1: docker-compose exec app ./manage.py migrate --fake registrar 0035_contenttypes_permissions
# step 2: docker-compose exec app ./manage.py migrate registrar 0036_create_groups
# step 3: fake run the latest migration in the migrations list
# [RECOMMENDED]
# Alternatively:
# step 1: duplicate the migration that loads data
# step 2: docker-compose exec app ./manage.py migrate

from django.db import migrations
from registrar.models import UserGroup
from typing import Any


# For linting: RunPython expects a function reference,
# so let's give it one
def create_groups(apps, schema_editor) -> Any:
    UserGroup.create_cisa_analyst_group(apps, schema_editor)
    UserGroup.create_full_access_group(apps, schema_editor)


class Migration(migrations.Migration):
    dependencies = [
        ("registrar", "0105_suborganization_domaingroup"),
    ]

    operations = [
        migrations.RunPython(
            create_groups,
            reverse_code=migrations.RunPython.noop,
            atomic=True,
        ),
    ]
