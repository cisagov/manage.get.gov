## Ticket

<!-- PR title format: `#issue_number: Descriptive name ideally matching ticket name - [sandbox]`-->
Resolves #00

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
- [ ] Update documentation in READMEs and/or onboarding guide

#### Ensured code standards are met (Original Developer)
<!-- Mark "- N/A" and check at the end of each check that is not applicable to your PR -->
- [ ] If any updated dependencies on Pipfile, also update dependencies in requirements.txt.
- [ ] Interactions with external systems are wrapped in try/except
- [ ] Error handling exists for unusual or missing values

#### Validated user-facing changes (if applicable)

- [ ] [Follow the process for requesting a design review](https://dhscisa.enterprise.slack.com/docs/T02QH7E1MHA/F06CZ6MRUKA). If code is not user-facing, delete design reviewer checklist
- [ ] Verify new pages have been added to .pa11yci file so that they will be tested with our automated accessibility testing
- [ ] Checked keyboard navigability
- [ ] screen reader (such as NVDA with Chrome or Voiceover with Safari):
  - [ ] Tested general usability
  - [ ] landmarks
  - [ ] page header structure
  - [ ] links
- [ ] Checked for errors or warnings with an a11y browser tool (such as ANDI or WAVE)

### As a code reviewer, I have

#### Reviewed, tested, and left feedback about the changes

- [ ] Pulled this branch locally and tested it
- [ ] Verified code meets all checks above. Address any checks that are not satisfied
- [ ] Reviewed this code and left comments. Indicate if comments must be addressed before code is merged
- [ ] Checked that all code is adequately covered by tests
- [ ] Verify migrations are valid and do not conflict with existing migrations

#### Validated user-facing changes as a developer
**Note:** Multiple code reviewers can share the checklists above, a second reviewer should not make a duplicate checklist. All checks should be checked before approving, even those labeled N/A.

- [ ] New pages have been added to .pa11yci file so that they will be tested with our automated accessibility testing
- [ ] Checked keyboard navigability
- [ ] Meets all designs and user flows provided by design/product
- [ ] screen reader (such as NVDA with Chrome or Voiceover with Safari):
  - [ ] Tested general usability
  - [ ] landmarks
  - [ ] page header structure
  - [ ] links
- [ ] Checked for errors or warnings with an a11y browser tool (such as ANDI or WAVE)
- [ ] (Rarely needed) Tested as both an analyst and applicant user

### As a designer reviewer, I have

#### Verified that the changes match the design intention

- [ ] Checked that the design translated visually
- [ ] Checked behavior. Comment any found issues or broken flows.
- [ ] Checked different states (empty, one, some, error)
- [ ] Checked for landmarks, page heading structure, and links

#### Validated user-facing changes as a designer

- [ ] Checked keyboard navigability
- [ ] Test [accessibility checklist](https://github.com/cisagov/manage.get.gov/blob/main/docs/dev-practices/code_review.md) using screen reader (such as NVDA with Chrome or Voiceover with Safari):
  - [ ] Tested general usability
  - [ ] Page structure
  - [ ] Links and buttons
  - [ ] Keyboard focus
- [ ] Checked for errors or warnings with an a11y browser tool (such as ANDI or WAVE)
- [ ] Tested with multiple browsers (check off which ones were used)
  - [ ] Chrome
  - [ ] Microsoft Edge
  - [ ] FireFox
  - [ ] Safari
- [ ] (Rarely needed) Tested as both an analyst and applicant user

### References
- [Code review best practices](../docs/dev-practices/code_review.md)

## Screenshots

<!-- If this PR makes visible interface changes, an image of the finished interface can help reviewers
and casual observers understand the context of the changes.
A before image is optional and can be included at the submitter's discretion.

Consider using an animated image to show an entire workflow.
You may want to use [GIPHY Capture](https://giphy.com/apps/giphycapture) for this! 📸

_Please frame images to show useful context but also highlight the affected regions._
--->
