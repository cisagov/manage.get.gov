# 2. Docker for development

Date: 2022-08-09

## Status

Accepted

## Context

Docker is widely accepted at TTS currently and in the development community at large. It works well with cloud.gov and is very portable to other cloud solutions.

The [Federal Audit Clearinghouse](https://github.com/GSA-TTS/FAC) project is a similar project to ours, from which we are taking many examples for reuse. FAC uses Docker.

Other options include using virtual machines or installing dependencies directly onto the host system. The first is not widely used at TTS; the second tends to cause problems with dependency management.

## Decision

To include a Dockerfile and docker-compose file.

## Consequences

We intend to deploy using containerized images; therefore, use of Docker on local will give the closest approximation to higher environments.

A greater technical burden may be placed on new employees during onboarding, if they have not already installed Docker and learned to use it.
