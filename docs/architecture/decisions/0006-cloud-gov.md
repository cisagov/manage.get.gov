# 6. Cloud.gov

Date: 2022-08-12

## Status

Accepted

## Context

We need a place to run our application for the registrar. Cloud.gov is a FIMSA Moderate Fedramped solution that supports our language and framework selections.

## Decision

To use cloud.gov to host our application(s). 

## Consequences

Choosing cloud.gov for our solution means we are locked into its opinionated choices for our infrastructure. It forces us to run 12-factor applications. It doesn't support brokering for services we may need like email notifications. 

It also means the compliance lift is much lighter. We do not need to prove we are compliance for the majority of our infrastructure and our runtime enviornment.
