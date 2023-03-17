# 19. Role-based Access Control

Date: 2023-03-17

## Status

Approved

## Context

In the registrar application, a single user might be associated with many
domains, and they might have different levels of access to view or change
those domains.

## Decision

To use a role-based access control system where we have a model of different
roles and an association that links a user to a specific role with a specified
role. Each role would have some associated permissions in the application and
we can enforce those permissions by using decorators on our Django views.

## Consequences

There is no enterprise model here of users belonging to an “organization” with
a role on all of its associated domain names. Instead, the association is
per-domain and a user would have to be granted the role on each domain
individually. There is also no process designed yet for how and whether users
can grant other users roles on a domain.

