# 21. Use Django Admin for Application Management

Date: 2023-06-22

## Status

Accepted

## Context

CISA needs a way to perform administrative actions to manage the new get.gov application as well as the .gov domain requests submitted. Analysts need to be able to view, review, and approve domain requests. Other
dashboard views, reports, searches (with filters and sorting) are also highly desired.

## Decision

Use Django's [Admin](https://docs.djangoproject.com/en/4.2/ref/contrib/admin/) site for administrative actions. Django
Admin gives administrators all the powers we anticipate needing (and more), with relatively little overhead on the
development team.

## Consequences

Django admin provides the team with a _huge_ head start on the creation of an administrator portal.

While Django Admin is highly customizable, design and development will be constrained by what is possible within Django
Admin.

We anticipate that this will, overall, speed up the time to MVP compared to building a completely custom solution.

Django Admin offers omnipotence for administrators out of the box, with direct access to database objects. This includes
the ability to put the application and its data in an erroneous state, based on otherwise normal business rules/logic.

In contrast to building an admin interface from scratch where development activities would predominantly
involve _building up_, leveraging Django Admin will require carefully _pairing back_ the functionalities available to
users such as analysts.

On accessibility: Django admin is almost fully accessible out-of-the-box, the exceptions being tables, checkboxes, and
color contrast. We have remedied the first 2 with template overrides and the 3rd with theming (see below).

On USWDS and theming: Django admin brings its own high level design framework. We have determined that theming on top of Django (scss)
is easy and worthwhile, while overwriting Django's templates with USWDS is hard and provides little return on investment
([research PR](https://github.com/cisagov/getgov/pull/831)).

While we anticipate that Django Admin will meet (or even exceed) the user needs that we are aware of today, it is still
an open question whether Django Admin will be the long-term administrator tool of choice. A pivot away from Django Admin
in the future would of course mean starting from scratch at a later date, and potentially juggling two separate admin
portals for a period of time while a custom solution is incrementally developed. This would result in an overall 
_increase_ to the total amount of time invested in building an administrator portal. 
