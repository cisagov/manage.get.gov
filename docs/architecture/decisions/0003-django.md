# 3. Django

Date: 2022-08-09

## Status

Accepted

## Context

Django is a web framework based on Python that has been in active development since 2005.

It follows a very standard MVC architecture (made popular by Ruby on Rails), although in Django parlance, a “view” is a controller (whereas the views are “templates”).

It comes with a robust object relational mapper for database access and includes a built-in admin interface suitable for simple use cases.

The [Federal Audit Clearinghouse](https://github.com/GSA-TTS/FAC) project is a similar project to ours, from which we are taking many examples for reuse. FAC uses Django.

Numerous other web frameworks exist in many languages, such as Ruby, PHP, Perl, Go, Elixir, etc. Other web frameworks exist in Python, such as Twisted and Flask.

## Decision

To use Django.

## Consequences

Django is well documented and approachable, even for people with limited programming experience.

We will have a dependency on the health of the Django project and the Python ecosystem at large.

Python is an interpreted language and will not have the same performance as compiled languages. Django is slower than its less featureful Python competitors (while being faster than Ruby on Rails, its nearest other-language competitor).

The job market for Django developers is currently (8/2022) strong, with 7,000 open positions on a popular career site.

Moving away from Django at a future point would require a complete rewrite of the codebase.
