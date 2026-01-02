# Copied from 0154_remove_waffle_flags.py
# Remove references to outdated flag name dns_prototype_flag which is now renamed to dns_hosting

from django.db import migrations, models


def remove_old_flags(apps, schema_editor):
    """
    Forward migration to delete the specified WaffleFlag objects
    """

    WaffleFlag = apps.get_model("registrar", "WaffleFlag")

    try:
        WaffleFlag.objects.get(name="dns_prototype_flag").delete()
    except WaffleFlag.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ("registrar", "0170_dnsrecord_dns_zone_dnszone_vendor_dns_zone_and_more"),
    ]

    operations = [
        migrations.RunPython(
            remove_old_flags,
            reverse_code=migrations.RunPython.noop,
            atomic=True,
        ),
    ]
