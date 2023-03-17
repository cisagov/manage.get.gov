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

## Permission decorator

The Django objects that need to be permission controlled are various views.
For that purpose, we add a very simple permission mixin
[`DomainPermission`](../../src/registrar/views/utility/mixins.py) that can be
added to a view to require that (a) there is a logged-in user and (b) that the
logged in user has a role that permits access to that view. This mixin is the
place where the details of the permissions are enforced. It can allow a view
to load, or deny access with various status codes, e.g. "403 Forbidden".

## Adding roles

The current MVP design uses only a single role called
`UserDomainRole.Roles.ADMIN` that has all access on a domain. As such, the
permission mixin doesn't need to examine the `role` field carefully. In the
future, as we add additional roles that our product vision calls for
(read-only? editing only some information?), we need to add conditional
behavior in the permission mixin, or additional mixins that more clearly
express what is allowed for those new roles.
