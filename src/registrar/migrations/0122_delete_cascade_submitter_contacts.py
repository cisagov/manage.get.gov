from django.db import migrations
from django.db.models import Q
from typing import Any


# Deletes Contact objects associated with a submitter which we are deprecating
def cascade_delete_submitter_contacts(apps, schema_editor) -> Any:
    contacts_model = apps.get_model("registrar", "Contact")
    submitter_contacts = contacts_model.objects.filter(
        Q(submitted_domain_requests__isnull=False)
        | Q(submitted_domain_requests_information__isnull=False)
        | Q(information_senior_official__isnull=True)
        | Q(senior_official__isnull=True)
        | Q(contact_domain_requests_information__isnull=True)
        | Q(contact_domain_requests__isnull=True)
    )
    submitter_contacts.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("registrar", "0121_alter_domaininformation_submitter_and_more"),
    ]

    operations = [
        migrations.RunPython(cascade_delete_submitter_contacts, reverse_code=migrations.RunPython.noop, atomic=True),
    ]
