# Django admin user roles

For our MVP, we create and maintain 2 admin roles:
Full access and CISA analyst. Both have the role `staff`.
Permissions on these roles are set through groups:
`full_access_group` and `cisa_analysts_group`. These
groups and the methods to create them are defined in
our `user_group` model and run in a migration.

For more details, refer to the [user group model](../../src/registrar/models/user_group.py).

## Adding a user as analyst or granting full access via django-admin (/admin)

If a new team member has joined, then they will need to be granted analyst (`cisa_analysts_group`) or full access (`full_access_group`) permissions in order to view the admin pages. These admin pages are the ones found at manage.get.gov/admin.
To do this, do the following:

1. The user in question will need to have a login.gov account and login into our system, this will create a `Users` table entry with their email address and name.
2. On that `Users` table note that the `GROUP` column should be blank for them as they have no special permissions yet.
3. Click on their username, then scroll down to the `User Permissions` section.
4. Under `User Permissions`, see the `Groups` table which has a column for `Available groups` and `Chosen groups`. Select the permission you want from the `Available groups` column and click the right arrow to move it to the  `Chosen groups`. Note, if you want this user to be an analyst select `cisa_analysts_group`, otherwise select the `full_access_group`.
5. (Optional) If the user needs access to django admin (such as an analyst), then you will also need to make sure "Staff Status" is checked. This can be found in the same `User Permissions` section right below the checkbox for `Active`.
6. Click `Save` to apply all changes.

## Removing a user group permission via django-admin (/admin)

If an employee was given the wrong permissions or has had a change in roles that subsequently requires a permission change, then their permissions should be updated in django-admin. Much like in the previous section you can accomplish this by doing the following:

1. Go to the `Users` table an select the username for the user in question
2. Scroll down to the `User Permissions` section and find the `Groups` table which has a column for `Available groups` and `Chosen groups`.
3. In this table, select the permission you want to remove from the `Chosen groups` and then click the left facing arrow to move the permission to `Available groups`.
4. Depending on the scenario you may now need to add the opposite permission group to the `Chosen groups` section, please see the section above for instructions on how to do that.
5. If the user should no longer see the admin page, you must ensure that under `User Permissions`, `Staff status` is NOT checked.
6. Click `Save` to apply all changes.

## Editing group permissions through code

We can edit and deploy new group permissions by:

1. Editing `user_group` then:
2. Duplicating migration `0036_create_groups_01`
and running migrations (append the name with a version number
to help django detect the migration eg 0037_create_groups_02)
3. Making sure to update the dependency on the new migration with the previous migration.