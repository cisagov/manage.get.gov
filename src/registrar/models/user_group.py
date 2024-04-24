from django.contrib.auth.models import Group
import logging

logger = logging.getLogger(__name__)


class UserGroup(Group):
    """
    UserGroup sets read and write permissions for superusers (who have full access)
    and analysts. For more details, see the dev docs for user-permissions.
    """

    class Meta:
        verbose_name = "User group"
        verbose_name_plural = "User groups"

    def create_cisa_analyst_group(apps, schema_editor):
        """This method gets run from a data migration."""

        # Hard to pass self to these methods as the calls from migrations
        # are only expecting apps and schema_editor, so we'll just define
        # apps, schema_editor in the local scope instead
        CISA_ANALYST_GROUP_PERMISSIONS = [
            {
                "app_label": "auditlog",
                "model": "logentry",
                "permissions": ["view_logentry"],
            },
            {
                "app_label": "registrar",
                "model": "contact",
                "permissions": ["change_contact"],
            },
            {
                "app_label": "registrar",
                "model": "domainrequest",
                "permissions": ["change_domainrequest"],
            },
            {
                "app_label": "registrar",
                "model": "domain",
                "permissions": ["view_domain"],
            },
            {
                "app_label": "registrar",
                "model": "user",
                "permissions": ["analyst_access_permission", "change_user"],
            },
            {
                "app_label": "registrar",
                "model": "domaininvitation",
                "permissions": ["add_domaininvitation", "view_domaininvitation"],
            },
            {
                "app_label": "registrar",
                "model": "userdomainrole",
                "permissions": ["view_userdomainrole", "delete_userdomainrole"],
            },
            {
                "app_label": "registrar",
                "model": "verifiedbystaff",
                "permissions": ["add_verifiedbystaff", "change_verifiedbystaff", "delete_verifiedbystaff"],
            },
            {
                "app_label": "registrar",
                "model": "federalagency",
                "permissions": ["add_federalagency", "change_federalagency", "delete_federalagency"],
            },
        ]

        # Avoid error: You can't execute queries until the end
        # of the 'atomic' block.
        # From django docs:
        # https://docs.djangoproject.com/en/4.2/topics/migrations/#data-migrations
        # We can’t import the Person model directly as it may be a newer
        # version than this migration expects. We use the historical version.
        ContentType = apps.get_model("contenttypes", "ContentType")
        Permission = apps.get_model("auth", "Permission")
        UserGroup = apps.get_model("registrar", "UserGroup")

        logger.info("Going to create the Analyst Group")
        try:
            cisa_analysts_group, _ = UserGroup.objects.get_or_create(
                name="cisa_analysts_group",
            )

            cisa_analysts_group.permissions.clear()

            for permission in CISA_ANALYST_GROUP_PERMISSIONS:
                app_label = permission["app_label"]
                model_name = permission["model"]
                permissions = permission["permissions"]

                # Retrieve the content type for the app and model
                content_type = ContentType.objects.get(app_label=app_label, model=model_name)

                # Retrieve the permissions based on their codenames
                permissions = Permission.objects.filter(content_type=content_type, codename__in=permissions)

                # Assign the permissions to the group
                cisa_analysts_group.permissions.add(*permissions)

                # Convert the permissions QuerySet to a list of codenames
                permission_list = list(permissions.values_list("codename", flat=True))

                logger.debug(
                    app_label
                    + " | "
                    + model_name
                    + " | "
                    + ", ".join(permission_list)
                    + " added to group "
                    + cisa_analysts_group.name
                )

                cisa_analysts_group.save()
                logger.debug("CISA Analyst permissions added to group " + cisa_analysts_group.name)
        except Exception as e:
            logger.error(f"Error creating analyst permissions group: {e}")

    def create_full_access_group(apps, schema_editor):
        """This method gets run from a data migration."""

        Permission = apps.get_model("auth", "Permission")
        UserGroup = apps.get_model("registrar", "UserGroup")

        logger.info("Going to create the Full Access Group")
        try:
            full_access_group, _ = UserGroup.objects.get_or_create(
                name="full_access_group",
            )
            # Get all available permissions
            all_permissions = Permission.objects.all()

            # Assign all permissions to the group
            full_access_group.permissions.add(*all_permissions)

            full_access_group.save()
            logger.debug("All permissions added to group " + full_access_group.name)
        except Exception as e:
            logger.error(f"Error creating full access group: {e}")
