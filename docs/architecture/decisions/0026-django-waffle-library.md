# 26. Django Waffle library for Feature Flags

Date: 2024-07-06

## Status

Approved

## Context

We release finished code twice weekly, allowing features to reach users quickly. However, several upcoming features require a series of changes that will need to be done over a few sprints and should only be displayed to users once we are all done. Thus, users would see half-finished features if we followed our standard process.

At the same time, some of these features should only be turned on for users upon request (and likely during user research). We would want a way for our CISA users to turn this feature on and off for people without requiring a lengthy process or code changes.

This brought us to finding solutions that could fix one or both of these problems.

## Considered Options

**Option 1:** Environment variables
The environment allows developers to set a true or false value to the given variable, allowing implementation over multiple sprints when new features are encapsulated with this variable. The feature shows when the variable is on (true); otherwise, it remains hidden. Environment variables are also innate to Django, making them free to use; on top of that, we already use them for other things in our code.

The downside is that you would need to go to cloud.gov or use the cf CLI to see the current settings on a sandbox. This is very technical, meaning only developers would really be able to see what features were set, and we would be the only ones able to adjust them. It would also be easy to accidentally have the feature on or off without noticing. This also would not solve the problem of turning features on and off quickly for a given user group.

**Option 2:** Feature branches
Like environment variables, using feature branches would be free and allow us to iterate on developing big features over multiple sprints. We would make a feature branch that developers working on that feature would push and pull from to iterate on. This quickly brings us to the downsides of this approach.

Using feature branches, we do not solve the problem of being able to turn features on and off quickly for a user group. More importantly, by working in a separate branch for more than a sprint, we easily risk having out-of-sync migrations and merge conflicts that would slow development time and cause frustration. Out-of-sync migrations can also cause technical issues on sandboxes, further contributing to development frustration.

**Option 3:** Feature flags
Feature flags are free, allowing us to implement features over multiple sprints, and some libraries can apply features based on UserGroups while even more come with an interface for non-developers to control turning feature flags on and off. Going with this decision would also entail picking the correct library or product.

**Option 3a:** Feature flags with Waffle
The Waffle feature flag library is a highly recommended Django library for handling large features. It has clear documentation on turning on feature flags for user groups, which is one of the main problems it attempts to solve. It also provides "Samples" that can turn on flags for a certain percentage of users and "Switches" that can be used to turn features on and off holistically. The reviews from those who used it were highly favorable, some even mentioning how it beat out competitors like Gargoyl. It's also compatible with Django admin, providing a quick way to add the view of the flags in Django admin so any user with admin access can modify flags for their sandbox.

The repo has had new releases every year since its the creation and looks to be well maintained, with many issues on the repo referring to new feature requests. 

**Option 3b:** Feature flags with Gargoyl
Gargoyl is another feature-flag library with Django, but it is no longer maintained, and reviews say it wasn't as easy to work with as Waffle. Using it would require forking the library, and many outstanding issues indicate bugs that need fixing. The mixed reviews from those who have done this and the less robust documentation were immediately huge cons to using this as an option.

**Option 3c:** Paid feature flag system with GitHub integration- LaunchDarkly
LaunchDarkly is a Fedramped solution with excellent reviews for controlling feature flags straight from GitHub to promote any team member easily controlling feature flags. However, the big con to this was that it would be a paid solution and would take time to procure, thus slowing down our ability to start on these significant features. We shouldn't consider LaunchDarkly because taking time to procure it would negatively affect our timeline, even if the budget was eventually approved.

## Decision
Option 3a, feature flags with the Django Waffle library

## Consequences
We are now reliant on the Waffle library for feature flags. As with any library, we would need to fork it if it ever became non-maintained with critical bugs. This doesn't seem likely in the near future, but if it occurred, we could complete the forking and fix any bug within a sprint without drastically impacting our timeline.