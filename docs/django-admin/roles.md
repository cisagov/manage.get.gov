# Django admin user roles

For our MVP, we create and maintain 2 admin roles:
Full access and CISA analyst. Both have the role `staff`.
Permissions on these roles are set through groups:
`full_access_group` and `cisa_analysts_group`. These
groups and the methods to create them are defined in
our `user_group` model and run in a migration.

For more details, refer to the [user group model](../../src/registrar/models/user_group.py).

## Editing group permissions through code

We can edit and deploy new group permissions by:

1. Editing `user_group` then:
2. Duplicating migration `0036_create_groups_01`
and running migrations (append the name with a version number
to help django detect the migration eg 0037_create_groups_02)
3. Making sure to update the dependency on the new migration with the previous migration