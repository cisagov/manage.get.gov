# 7. Python Buildpack

Date: 2022-08-12

## Status

Accepted

## Context

We had previously drafted ADRs to use Docker to build images for containerized deployment. The motivation was to reduce dependency on Cloud.gov. These ADRs were rejected, mainly owing to the necessity of having an image repository to hold the built images. The team had concerns about an overreliance on GitHub with their GitHub Packages service and about the overall maintenance burden of any image repository.

Cloud.gov uses Cloud Foundry which provides several “buildpacks”. These are automated environments which will take a code repository of a certain language and do the usual setup steps to prepare a deployment of that code. In the case of Python, this means automated detection of Pipfile and installation of packages.

We do not anticipate needing a custom buildpack, because our current use case falls completely within the Python buildpack's purview.

## Decision

To use Cloud Foundry’s Python buildpack.

## Consequences

There will be a small amount of future work if the code is migrated off of Cloud.gov, but only a small amount. Proportionate to the overall effort of migration, it is inconsequential.

Cloud.gov provides [documentation around the trade-offs](https://cloud.gov/docs/deployment/docker/):

|   |  Supported buildpack | Docker container  |
|---|---|---|
|Pros|It “just works”. Automatic and constant security updates. All you need to do is write code.|Can build container images and run containers on local workstation. Fine-grained control over compilation and root filesystem.|
|Cons|Difficult to recreate the execution environment locally. Testing compilation and the result of staging is harder.|Added responsibility for all security updates and bug fixes. More compliance responsibility means more work.|
