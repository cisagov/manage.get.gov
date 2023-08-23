# 6. Cloud.gov

Date: 2022-08-12

## Status

Accepted

## Context

We need a place to run our application for the registrar. Cloud.gov is a FISMA Moderate FedRAMP'd solution that supports our language and framework selections.

## Decision

To use cloud.gov to host our application(s). 

## Consequences

* Choosing Cloud.gov for our solution means we are assisted by its opinionated choices for our infrastructure. For example, it forces us to run 12-factor applications.
* It doesn't support brokering for services we may need like email notifications.
* The compliance lift is lighter. We can inherit Cloud.gov's controls for the majority of our infrastructure and our runtime enviornment.

## Alternatives Considered

Run our application on in either CISA's Azure or AWS environment with a containerized deployment.
