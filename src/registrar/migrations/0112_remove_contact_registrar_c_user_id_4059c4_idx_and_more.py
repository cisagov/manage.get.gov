# Generated by Django 4.2.10 on 2024-07-02 19:52

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("registrar", "0111_create_groups_v15"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="contact",
            name="registrar_c_user_id_4059c4_idx",
        ),
        migrations.RemoveField(
            model_name="contact",
            name="user",
        ),
    ]
