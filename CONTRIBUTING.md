# Contributing to the .gov registrar

Thanks for your interest in contributing to the .gov registrar!

The .gov domain helps U.S.-based government organizations build public trust by making their official services easier to identify online. As part of our commitment to transparency, the .gov registrar is developed in the open. We welcome community feedback, ideas, bug reports, documentation improvements, and code contributions.

The registrar has an active development team, backlog, and [public roadmap](https://github.com/orgs/cisagov/projects/100). To help contributors make informed decisions about where to spend their time, there are a few things to know before starting a contribution.

## Ways to contribute

Contributions don't need to include code. Useful contributions include:

* Reporting bugs  
* Suggesting features or improvements  
* Reporting accessibility or usability problems  
* Improving documentation  
* Contributing code (see notes below on [contributing code](#before-working-on-a-code-change))

### Bug reports

You may report a bug by creating a [bug issue](https://github.com/cisagov/manage.get.gov/issues/new?template=bug.yml) in this repository or by emailing our support team at help@get.gov.

Please provide enough information for us to understand and, when possible, reproduce the problem, including:

* Steps to reproduce the issue  
* Expected behavior  
* Current behavior  
* Other relevant information, such as browser type or whether you are using a desktop or mobile device

**Do not report security or privacy vulnerabilities through a public GitHub issue.** See [Reporting security and privacy vulnerabilities](#reporting-security-and-privacy-vulnerabilities).

### Feature requests

You may suggest a feature or improvement by creating an [issue](https://github.com/cisagov/manage.get.gov/issues/new?template=BLANK_ISSUE) in this repository or emailing help@get.gov.

Please include:

* The requesting government organization or team, if applicable;  
* The problem you would like solved; and  
* Context about the need or use case.

## Before working on a code change

The .gov team maintains a [public roadmap](https://github.com/orgs/cisagov/projects/100) to organize upcoming work and communicate our current plans and priorities. The roadmap is a planning tool and does not represent a commitment to deliver particular work or to deliver it on a particular timeline.

Most issues in this repository are part of the project's backlog and are intended to be worked on by the development team. Many have not been prioritized.

Because the .gov registrar has an active development team and roadmap, we cannot guarantee that an unsolicited pull request or code change will be reviewed in a timely manner or merged, even when the proposed change is reasonable or technically sound.

Before working on a code change, we encourage you to review the roadmap, related issues and pull requests, [current](https://github.com/orgs/cisagov/projects/26) and [upcoming sprint](https://github.com/orgs/cisagov/projects/26/views/25) boards, and recent repository activity first. This may help surface work that is already underway or related to other planned changes. However, there may be context, dependencies, or work in progress that are not apparent from the public repository. You are welcome to leave a comment on an issue that is interesting to you and suggest an approach.

## Protect sensitive information

This is a public repository. Do not commit or include in issues, pull requests, screenshots, test data, or other repository content:

* Personally identifiable information (PII), including information obtained through user research, interviews, or feedback;  
* User research scheduling information or other non-public research documentation;  
* Information about particular vendors or non-public procurement information;  
* Credentials, API keys, tokens, private keys, or other secrets;  
* Private registrant or account information; or  
* Non-public compliance or infrastructure information, including IP addresses when that information is not intended for public release.

Use fictitious or appropriately sanitized data in tests, fixtures, examples, screenshots, and documentation.

If you are unsure whether information is appropriate for this public repository, do not post it publicly. Contact the .gov team at help@get.gov for guidance.

## Pull requests

We appreciate external contributions and the time contributors put into them. We evaluate pull requests based on project priorities, technical fit, maintainability, security, privacy, accessibility, testing requirements, and available maintainer capacity.

A pull request may be closed without being merged if:

* The work is already planned or underway  
* It does not fit the project's current direction  
* We do not have the capacity to adequately evaluate the contribution.

When we can, we may explain why a contribution is not being accepted and may identify another way to provide useful feedback.

### Preparing a pull request

Keep pull requests focused on the change being proposed. Avoid unrelated refactoring, dependency upgrades, formatting changes, or other cleanup unless they are necessary for the contribution.

When changing behavior, include or update tests when practical. For security reasons, external contributions will not trigger most of our CI/CD pipelines. If an external contribution is reviewed as safe, a member of the .gov team will run the pipeline before a change can be merged. We encourage you to run tests locally where possible ahead of submitting a pull request.

### Branch names

Use a brief, descriptive name for your branch.

Our team members use the branch naming convention `initials/issue-number-description`, for example:

`ab/1234-update-documentation`

Branches following the project team's naming convention may also integrate with development and sandbox workflows that are available to authorized team members.

## AI-assisted contributions

AI coding tools and agents may be used to contribute to this repository, but their use does not replace human review or responsibility for a contribution.

The human contributor is responsible for reviewing, validating, and submitting the resulting change and for ensuring that it complies with this contributing policy.

If an AI coding agent creates or substantially modifies repository content, or performs Git or GitHub actions on your behalf, disclose its involvement in the commits and pull request.

See `AGENTS.md` for attribution requirements and instructions that apply to AI coding agents working in this repository.

## Reporting security and privacy vulnerabilities

Do not disclose suspected security or privacy vulnerabilities in a public issue or pull request.

Please review the .gov [vulnerability disclosure policy](https://get.gov/vulnerability-disclosure-policy/) and this repo’s security policy for more details about reporting suspected vulnerabilities.

## License

As a work of the United States government, this project is in the public domain within the United States. The project also waives copyright and related rights worldwide through the CC0 1.0 Universal public domain dedication.

By contributing to this project, you agree that your contribution may be made available under these terms. See `LICENSE.md` for details.