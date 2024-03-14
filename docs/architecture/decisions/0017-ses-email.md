# 17. Use AWS SES for email sending

Date: 2022-02-14

## Status

Approved

## Context

Our application needs to be able to send email to applicants for various
purposes including notifying them that their domain request has been submitted.
We need infrastructure for programmatically sending email. Amazon Web Services
(AWS) provides the Simple Email Service (SES) that can do that. CISA can
provide access to AWS SES for our application.

## Decision

To use AWS SES to provide programmatic email-sending capability. 

## Consequences

We will be dependent on a manual external process to provision and configure
our AWS resources through CISA. We already use external network egress for
Login.gov configuration, so there is no additional network configuration
needed to be able to access the external AWS SES service. We now have two
additional secret credentials to manage in our environment for accessing the
external AWS services.
