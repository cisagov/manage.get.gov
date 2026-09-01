---
name: Developer Onboarding
about: Onboarding steps for new developers joining the .gov team.
title: 'Developer Onboarding: GH_HANDLE'
labels: dev, onboarding
assignees: ''

---

# Developer Onboarding

- Onboardee: _GH handle of person being onboarded_
- Onboarder: _GH handle of onboarding buddy_

### Steps for the onboardee

- [ ] E-mail leads your GitHub handle so we can add you to GitHub and assign this ticket to you
- [ ] Follow the [.gov onboarding dev setup instructions](https://docs.google.com/document/d/1SPe-pS8hGIaVOvFiLJLliGq0J4MY-3X4BzC-D2E2BO8/edit?tab=t.izb6sye9wyul#heading=h.fj87qaux1lx8).

### Steps for the onboarder

- [ ] Email github@cisa.dhs.gov to add the onboardee to the [CISA GitHub organization](https://github.com/getgov) and [.gov team](https://github.com/orgs/cisagov/teams/gov).
- [ ] Add the onboardee to the cloud.gov org (`cisa-dotgov`)
- [ ] Set up a [developer-specific space for the new developer](#setting-up-developer-sandbox-onboarder)
- [ ] Add the onboardee to our login.gov sandbox team (`.gov Registrar`) via the [dashboard](https://dashboard.int.identitysandbox.gov/)

## Documents to Review

- [ ] [Engineering Onboarding](https://docs.google.com/document/d/1SPe-pS8hGIaVOvFiLJLliGq0J4MY-3X4BzC-D2E2BO8/edit?tab=t.0)
- [ ] [Team Onboarding](https://docs.google.com/document/d/1ukbpW4LSqkb_CCt8LWfpehP03qqfyYfvK3Fl21NaEq8/edit?tab=t.0#heading=h.6dw0iz1u56ox)
- [ ] [Contributing Policy](https://github.com/cisagov/dotgov/tree/main/CONTRIBUTING.md)

## Setting up developer sandbox (onboarder)

We have three types of environments: stable, staging, and sandbox. Stable (production) and staging (pre-production) are deployed via tagged releases. Developer sandboxes let get.gov developers work in a production-like environment without disrupting stable or staging. Each sandbox is namespaced and will be deployed automatically when the appropriate branch syntax is used for that space in an open pull request.

All automation for setting up a developer sandbox is documented in the scripts for [creating a developer sandbox](https://github.com/cisagov/manage.get.gov/blob/main/ops/scripts/create_dev_sandbox.sh) and [removing a developer sandbox](https://github.com/cisagov/manage.get.gov/blob/main/ops/scripts/destroy_dev_sandbox.sh). A cloud.gov organization administrator must run the script to create the sandbox.

## Known Issues

### SSL Verification Failure

Some developers using Government Furnished Equipment (GFE) have problems using tools such as Git and pip due to SSL verification failures. This happens because GFE has a custom certificate chain installed, but these tools use their own certificate bundles. As a result, they cannot verify an SSL connection. To resolve this in pip, use `--use-feature=truststore` to direct pip to use the local certificate store. If you encounter this issue with Git on Windows, run `git config --global http.sslbackend schannel`.

If you encounter these issues in a Docker container, you will need to export the root certificate and add it to the container. Ask another developer how to do this properly.

### Puppeteer Download Error

When building the Node image either individually or with Docker Compose, there may be an error caused by the Puppeteer Node package. This can be resolved by adding `ENV PUPPETEER_SKIP_DOWNLOAD=true` to [node.Dockerfile](../../src/node.Dockerfile) after the `COPY` command.

### Checksum Error

There is an unresolved issue with Python package installation that occurs after the SSL verification failure above has been resolved. It often manifests as a checksum error where the hash of a downloaded `.whl` file (Python package) does not match the expected value. This appears to happen because pythonhosted.org cuts off download connections to some devices for some packages; the behavior is somewhat inconsistent. We have outstanding issues with PyPA and DHS IT to fix this.
