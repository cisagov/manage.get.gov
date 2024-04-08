# User Permissions

In our registrar application, we need authenticated users (via Login.gov) to
be able to access domains that they are authorized to and not to access
domains that they are not authorized to. In our initial MVP design, this
access is controlled at the domain level, there is no "enterprise" or
"organization" layer for assigning permissions in bulk. (See [this
ADR](../architecture/decisions/0019-role-based-access-control.md) for more on
that decision.)

## Data modeling

We need a way to associate a particular user with a particular domain and the
role or set of permissions that they have. We use a `UserDomainRole`
[model](../../src/registrar/models/user_domain_role.py) with `ForeignKey`s to
`User` and `Domain` and a `role` field. There are reverse relationships called
`permissions` for a user and for a domain to get a list of all of the
`UserDomainRole`s that involve the user or the domain. In addition, there is a
`User.domains` many-to-many relationship that works through the
`UserDomainRole` link table.

## Migrating changes to Analyst Permissions model
Analysts are allowed a certain set of read/write registrar permissions. 
Setting user permissions requires a migration to change the UserGroup 
and Permission models, which requires us to manually make a migration 
file for user permission changes. 
To update analyst permissions do the following:
1. Make desired changes to analyst group permissions in user_group.py.
2. Follow the steps in the migration file0037_create_groups_v01.py to 
create a duplicate migration for the updated user group permissions.
3. To migrate locally, run docker-compose up. To migrate on a sandbox,
push the new migration onto your sandbox before migrating.

## Permission decorator

The Django objects that need to be permission controlled are various views.
For that purpose, we have a View subclass to enforce user permissions on a
domain called
[`DomainPermissionView`](../../src/registrar/views/utility/permission_views.py)
that can be added to a view to require that (a) there is a logged-in user and
(b) that the logged in user has a role that permits access to that view. This
mixin is the place where the details of the permissions are enforced. It can
allow a view to load, or deny access with various status codes, e.g. "403
Forbidden".

In addition, we now require all of our application views to have a logged-in
user by using a Django middleware that makes every request "login required".
This is slightly belt-and-suspenders because our permissions view also checks
that the request includes a logged in user, but it avoids accidentally creating
content that is publicly available by accident. We can specifically mark a view
as "not login required" if we do need to have publicly accessible content (such
as health checks used by our platform).

## Adding roles

The current MVP design uses only a single role called
`UserDomainRole.Roles.MANAGER` that has all access on a domain. As such, the
permission mixin doesn't need to examine the `role` field carefully. In the
future, as we add additional roles that our product vision calls for
(read-only? editing only some information?), we need to add conditional
behavior in the permission mixin, or additional mixins that more clearly
express what is allowed for those new roles.

# Admin User Permissions

Refer to [Django Admin Roles](../django-admin/roles.md)
