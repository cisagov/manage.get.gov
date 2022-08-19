# 9. GitHub Actions

Date: 2022-08-11

## Status

Accepted

## Context

We need a tool to execute scripts whenever code is modified. These automated tools are called CI/CD pipelines. CI is continuous integration. CD is continuous deployment. These may be slight misnomers, as our project does not seek to integrate or deploy “continuously”.

We want certain tools, such as linters, test harnesses, and static security analysis to run each time new code is submitted via a pull request on GitHub.

We want certain other tools, such as build scripts and deployment scripts, to run whenever code is merged into the authoritative copy (our “main” branch in git).

Many CI/CD tools exist. Some top competitors in this space are GitLab CI/CD, CircleCI, TravisCI, and Jenkins.

GitHub Actions is an easy choice due to its tight integration with GitHub (the Microsoft product in which the code is currently stored).

## Decision

To use GitHub Actions.

## Consequences

The choice of CI/CD pipeline is more closely tied to the infrastructure of a project than to its codebase. It is expected that CI/CD pipeline scripts will need to be rewritten whenever a significant infrastructure change takes place.

Deployment keys–and perhaps other secrets–will be entrusted to Microsoft and will be vulnerable to technical failures, process failures, or policy failures on their part.
