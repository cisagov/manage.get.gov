# n. Django Templates

Date: 2022-09-26

## Status

Approved

## Context

In the context of doing server-side rendering ([ADR](./0008-server-side-rendering.md)), we need some templating engine on the backend which will take variables and insert them into HTML pages to be served to the end user.

## Decision

To use Django’s built-in templating engine.

## Consequences

While it admittedly has fewer capabilities compared to Jinja2, it has the advantage of being already available with no further configuration or dependencies.
