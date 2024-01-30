## Ticket

Resolves #00
<!--Reminder, when a code change is made that is user facing, beyond content updates, then the following are required:
- a developer approves the PR
- a designer approves the PR or checks off all relevant items in this checklist.

All other changes require just a single approving review.-->

## Changes

<!-- What was added, updated, or removed in this PR. -->
- Change 1
- Change 2

<!--
    Please add/remove/edit any of the template below to fit the needs
    of this specific PR.
--->

## Context for reviewers

<!--Background context, more in-depth details of the implementation, and anything else you'd like to call out or ask reviewers.  -->

## Setup

<!--  Add any steps or code to run in this section to help others run your code.
    
    Example 1:
    ```sh
    echo "Code goes here"
    ``` 
    
    Example 2: If the PR was to add a new link with a redirect, this section could simply be:
    -go to /path/to/start/page
    -click the blue link in the <insert location>
    -notice user is redirected to <proper end location>
-->

## Code Review Verification Steps

### As the original developer, I have

#### Satisfied acceptance criteria and met development standards

- [ ] Met the acceptance criteria, or will meet them in a subsequent PR
- [ ] Created/modified automated tests
- [ ] Added at least 2 developers as PR reviewers (only 1 will need to approve)
- [ ] Messaged on Slack or in standup to notify the team that a PR is ready for review
- [ ] Changes to “how we do things” are documented in READMEs and or onboarding guide
- [ ] If any model was updated to modify/add/delete columns, makemigrations was ran and the associated migrations file has been commited.

#### Ensured code standards are met (Original Developer)

- [ ] All new functions and methods are commented using plain language
- [ ] Did dependency updates in Pipfile also get changed in requirements.txt?
- [ ] Interactions with external systems are wrapped in try/except
- [ ] Error handling exists for unusual or missing values

#### Validated user-facing changes (if applicable)

- [ ] New pages have been added to .pa11yci file so that they will be tested with our automated accessibility testing
- [ ] Checked keyboard navigability
- [ ] Tested general usability, landmarks, page header structure, and links with a screen reader (such as Voiceover or ANDI)
- [ ] Add at least 1 designer as PR reviewer

### As a code reviewer, I have

#### Reviewed, tested, and left feedback about the changes

- [ ] Pulled this branch locally and tested it
- [ ] Reviewed this code and left comments
- [ ] Checked that all code is adequately covered by tests
- [ ] Made it clear which comments need to be addressed before this work is merged
- [ ] If any model was updated to modify/add/delete columns, makemigrations was ran and the associated migrations file has been commited.

#### Ensured code standards are met (Code reviewer)

- [ ] All new functions and methods are commented using plain language
- [ ] Interactions with external systems are wrapped in try/except
- [ ] Error handling exists for unusual or missing values
- [ ] (Rarely needed) Did dependency updates in Pipfile also get changed in requirements.txt?

#### Validated user-facing changes as a developer

- [ ] New pages have been added to .pa11yci file so that they will be tested with our automated accessibility testing
- [ ] Checked keyboard navigability
- [ ] Meets all designs and user flows provided by design/product
- [ ] Tested general usability, landmarks, page header structure, and links with a screen reader (such as Voiceover or ANDI)

- [ ] Tested with multiple browsers, the suggestion is to use ones that the developer didn't (check off which ones were used)
  - [ ] Chrome
  - [ ] Microsoft Edge
  - [ ] FireFox
  - [ ] Safari

- [ ] (Rarely needed) Tested as both an analyst and applicant user

**Note:** Multiple code reviewers can share the checklists above, a second reviewers should not make a duplicate checklist

### As a designer reviewer, I have

#### Verified that the changes match the design intention

- [ ] Checked that the design translated visually
- [ ] Checked behavior
- [ ] Checked different states (empty, one, some, error)
- [ ] Checked for landmarks, page heading structure, and links
- [ ] Tried to break the intended flow

#### Validated user-facing changes as a designer

- [ ] Checked keyboard navigability
- [ ] Tested general usability, landmarks, page header structure, and links with a screen reader (such as Voiceover or ANDI)

- [ ] Tested with multiple browsers (check off which ones were used)
  - [ ] Chrome
  - [ ] Microsoft Edge
  - [ ] FireFox
  - [ ] Safari

- [ ] (Rarely needed) Tested as both an analyst and applicant user

## Screenshots

<!-- If this PR makes visible interface changes, an image of the finished interface can help reviewers
and casual observers understand the context of the changes.
A before image is optional and can be included at the submitter's discretion.

Consider using an animated image to show an entire workflow.
You may want to use [GIPHY Capture](https://giphy.com/apps/giphycapture) for this! 📸

_Please frame images to show useful context but also highlight the affected regions._
--->
