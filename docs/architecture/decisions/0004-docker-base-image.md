# 4. Docker base image

Date: 2022-08-09

## Status

Accepted

## Context

In containerized builds, it is rare to start from scratch. The project’s Dockerfile should specify a base image from which to build.

The [python page on Docker Hub](https://hub.docker.com/_/python) has a discussion of what various image variants contain.

Python images can be scoped to specific versions, such as 3.8.6, or to more generic versions, such as 3. There is a slim variant for smaller image size and variants scoped to specific versions of Debian.

Alpine is a popular base image due to its small size and fast build times. However, it may not be the best choice for Python projects, due to its use of musl over glibc. Here’s a [blog post explaining this](https://pythonspeed.com/articles/alpine-docker-python/).

## Decision

To use python:3.

## Consequences

The python:3 image may or may not be secure enough for the long term needs of the project.

Using python:3 ensures that minor version upgrades will be automatically performed each time the image is built. The consequence is that the code may break unexpectedly, if a minor version introduces an incompatibility. The risk of this is low, as the Python team strives for semantic versioning, but is not zero.

Likewise, not pinning to the underlying Debian release ensures that the image will use the latest stable release at each build, with the same risk and benefit trade-off.
