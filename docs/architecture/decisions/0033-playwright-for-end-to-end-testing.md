# 33. Use Playwright for End To End Testing

Date: 2026-10-21

## Status

In Review

## Context

We would like to incorporate end to end testing within the manage.gov application. The framework should be able to complete the domain registration flow (login -> domain creation -> domain approval) and be run as part of the CI/CD process through GitHub Actions. Playwright offers a comprehensive test suite allowing for cross-browswer support with parallel execution capabilities for increased performance.

## Decision

To use Playwright for end to end testing. We also considered using Cypress but ultimately went with Playwright as it offers better browser compatibility (Cypress does not cover Safari) as well as functioning better for non-SPA applications. Playwright also has better performance metrics and includes parrelelization which Cypress charges extra for.

## Consequences

Adding a new GitHub action could cause further slowdowns with the already overloaded self-hosted runners.