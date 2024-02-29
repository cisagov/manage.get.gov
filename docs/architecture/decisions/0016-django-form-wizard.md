# 16. Django Form Wizard

Date: 2022-01-03

## Status

Accepted

## Context

The domain request form by which registrants apply for a .gov domain is presented over many pages.

Because we use server-side rendering, each page of the domain request is a unique HTML page with form fields surrounded by a form tag.

Needing a way to coordinate state between the pages as a user fills in their domain request, we initially used the Form wizard from [django-formtools](https://django-formtools.readthedocs.io/en/latest/wizard.html). This eventually proved unworkable due to the lack of native ability to have more than one Django form object displayed on a single HTML page.

However, a significant portion of the user workflow had already been coded, so it seemed prudent to port some of the formtools logic into our codebase.

## Decision

To maintain each page of the domain request as its own Django view class, inheriting common code from a parent class.

To maintain Django form and formset class in accordance with the Django models whose data they collect, independently of the pages on which they appear.

## Consequences

The wizard implementation is now unique to our codebase, which will impact developer onboarding, in the form of additional time needed to understand how it works.

A small amount of additional code to maintain is introduced. Impact is likely to be minor. Library functions which were not needed by our implementation were not ported.
