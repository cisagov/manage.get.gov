# 12. Use custom User model with separate UserProfile

Date: 2022-09-26

## Status

Superseded by [20. User models revisited, plus WHOIS](./0020-user-models-revisited-plus-whois.md)

## Context

Django strongly recommends that a new project use a custom User model in their
first migration
<https://docs.djangoproject.com/en/4.1/topics/auth/customizing/#using-a-custom-user-model-when-starting-a-project>.
This allows for future customization which would not be possible at a later
date if it isn’t done first.

In order to separate authentication concerns from various user-related details
we might want to store, we want to decide how and where to store that
additional information.

## Decision

We use a custom user model derived from Django’s django.contrib.auth.User as
recommended along with a one-to-one related UserProfile model where we can
separately store any particular information about a user that we want to. That
includes contact information and the name that a person wants to use in the
application.

Because the UserProfile is a place to store additional information about a
particular user, we mark each row in the UserProfile table to “cascade” deletes
so that when a single user is deleted, the matching UserProfile will also be
deleted.

## Consequences

If a user in our application is deleted (we don’t know at this point how or
when that might happen) then their profile would disappear. That means if the
same person returns to the application and makes a new account, there will be
no way to get back their UserProfile information and they will have to re-enter
it.
