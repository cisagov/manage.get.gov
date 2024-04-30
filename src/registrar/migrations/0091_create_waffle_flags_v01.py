# This migration creates default WaffleFlag objects for our DB.
# Whenever you add to the `create_waffle_flags` function, increment/copy this
# migration by one

from django.db import migrations
from registrar.models import WaffleFlag
from typing import Any


# For linting: RunPython expects a function reference,
# so let's give it one
def create_flags():
    """
    Populates pre-existing flags we wish to associate.
    Only generates a flag name and a note, but no other data is loaded at this point.
    """
    WaffleFlag.create_waffle_flags_for_migrations()

def delete_flags():
    """
    Deletes all prexisting flags. 
    Does not delete flags not defined in this scope (user generated).
    """
    WaffleFlag.delete_waffle_flags_for_migrations()


class Migration(migrations.Migration):
    dependencies = [
        ("registrar", "0090_waffleflag"),
    ]

    operations = [
        migrations.RunPython(
            code=create_flags,
            reverse_code=delete_flags,
            atomic=True,
        ),
    ]
