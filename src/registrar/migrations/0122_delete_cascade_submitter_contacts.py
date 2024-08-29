from django.db import migrations
from typing import Any


# Deletes Contact objects associated with a submitter which we are deprecating
def cascade_delete_submitter_contacts(apps, schema_editor) -> Any:
    contacts_model = apps.get_model("registrar", "Contact")
    submitter_contacts = contacts_model.objects.filter(submitted_domain_requests__isnull=False)
    submitter_contacts.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("registrar", "0121_alter_domaininformation_submitter_and_more"),
    ]

    operations = [
        migrations.RunPython(cascade_delete_submitter_contacts, reverse_code=migrations.RunPython.noop, atomic=True),
    ]
