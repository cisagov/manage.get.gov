# Contributing

## What not to commit to the repo

There are a handful of things we do not commit to the repository:
- Information about particular vendors or procurement information
- Anything related to PII whether it is from user interviews or feedback
- User research related scheduling or documentation
- Compliance documentation that includes IP addresses
- Secrets of any kind

## Project Management

We use [Github Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects) for project management and tracking.

### Github Project Board

We maintain an internal [Github Project Board](https://github.com/orgs/cisagov/projects/26) for tracking issues across .gov related repositories. Draft issues in the board are private and any project related issues are public.

### Labeling system

Every issue in this respository and on the project board should be appropriately [labeled](https://github.com/cisagov/dotgov/issues/labels). Each sprint we identify one or more `epic` issues that express our goals for the sprint. Within the epic we document all related issues that must be shipped for the epic to move to done.

We also have labels for each discipline and for research and project management related tasks. While this repository and project board track development work, we try to document all work related to the project here as well. 

## Pull request etiquette

- The submitter is in charge of merging their PRs unless the approver is given explicit permission.
- Do not commit to another person's branch unless given explicit permission.
- Keep pull requests as small as possible. This makes them easier to review and track changes.
- Bias towards approving i.e. "good to merge once X is fixed" rather than blocking until X is fixed, requiring an additional review.
- Write descriptive pull requests. This is not only something that makes it easier to review, but is a great source of documentation. 

## Branch Naming

Our branch naming convention is `name/topic-or-feature`, for example: `lmm/add-contributing-doc`. 
