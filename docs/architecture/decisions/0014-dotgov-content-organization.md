# 14. Use existing Cloud.gov Pages site for content, Django app for registrar functionality

Date: 2022-10-04

## Status

Proposed

## Context

Currently web infrastructure for the dotgov program is split between a [home site hosted on Cloud.gov Pages](https://home.dotgov.gov/) and the registrar/registry [hosted by Verisign](https://domains.dotgov.gov/dotgov-web/). The two sites provide very different experiences, confusingly different domains, and don’t share the same technical infrastructure. As we award a new contract that formally splits the registry/registrar functions, we have an opportunity to reimagine how users learn about .gov and how they register and manage domains.

## Decision

Keep the Cloud.gov Pages site for program content (About, Guides, News, Docs, etc.) and as the front page for program services. Use the Django application we are building to solely host the registrar behind login.gov. Move the Cloud.gov Pages site to get.gov, and host the Django site at the subdomain registrar.get.gov. Both will use USWDS with the same settings. 

This allows us to manage content separately from our application code. This both lets us write content in a markdown format rather than HTML in our application and update content without rebuilding the application. 

## Consequences

This means we have to maintain two systems: Cloud.gov Pages and the Django app running in our Cloud.gov organization. When we have to update style settings for one, we will have to update the settings for the other.  
