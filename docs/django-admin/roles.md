# Django admin user roles

For our MVP, we create and maintain 2 admin roles:
Full access and CISA analyst. Both have the role `staff`.
Permissions on these roles are set through groups:
`full_access_group` and `cisa_analysts_group`. These
groups and the methods to create them are defined in
our `user_group` model and run in a migration.

## Editing group permissions through code

We can edit and deploy new group permissions by
editing `user_group` then:

- Duplicating migration `0036_create_groups`
and running migrations (RECOMMENDED METHOD), or

- Fake the previous migration to run an existing create groups migration:
 - step 1: docker-compose exec app ./manage.py migrate --fake registrar 0035_contenttypes_permissions
 - step 2: docker-compose exec app ./manage.py migrate registrar 0036_create_groups
 - step 3: fake run the latest migration in the migrations list