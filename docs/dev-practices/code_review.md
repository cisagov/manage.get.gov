## Code Review

After creating a pull request, pull request submitters should:
- Add at least 2 developers as PR reviewers (only 1 will need to approve).
- Message on Slack or in standup to notify the team that a PR is ready for review.
- If any model was updated to modify/add/delete columns, run makemigrations and commit the associated migrations file.
- If any updated dependencies on Pipfile, also update dependencies in requirements.txt.

Code changes on user-facing features (excluding content updates) require approval from at least one developer and one designer.
All other changes require just a single approving review.

## Pull Requests for User-facing changes
When making user-facing changes, test that your changes work on multiple browsers including Chrome, Microsoft Edge, Firefox, and Safari.

## Coding standards
(The Coding standards section may be moved to a new code standards file in a future ticket.
For now we're simply moving PR template content into the code review document for consolidation)

### Plain language
All functions and methods should use plain language.

TODO: Plain language description and examples in code standards ticket.