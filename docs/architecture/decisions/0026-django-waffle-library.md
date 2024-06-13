# 24. Production Release Cadence

Date: 2024-07-06

## Status

Approved

## Context

We release finished code twice a week allowing features to reach users fast. However, several upcoming features required a series of changes that would need to be done over a couple sprints and should not display to users until we are all done. Thus, if we followed our normal process, users would see half-finished features.

At the same time, some of these features should only be turned on for users upon request (and likely during user research). We would want a way for our CISA users to be able to turn this feature on and off for people without requiring a lengthy process or code changes.

This brought us to finding solutions that could fix one or both of these problems.


## Considered Options

**Option 1:** Environment variables
Environment variables would allow implementation over multiple sprints, by allowing us to set a true or false value to the given variable. When the varaible is on (true) the feature shows, otherwise it remains hidden. ANother benefit is that it is free and we already use environment variables for other things in our code.

The down side, is that to see what the current setting is on a sandbox you would need to go to cloud.gov or use the cf cli to see the current settings. This is very technical, meaning only developers would really be able to see what features were set and we would be the only ones to adjust them. It would also be really easy to accidentally have the feature on or off without noticing. This also would not solve the problem of being able to turn features on and off easily for a given user group.
**Option 2:** Feature branches
Like environrment variables, using feature branches would be free and allow us to iterate on development of big features over multiple sprints. We would make a feature branch that developers working on that feature would push and pull from to iterate on. This quickly brings us to the downsides of this approach.

WIth feature branches we do not solve the problem of being able to turn features on and off easily for a user group. More importantly, by working in a seperated branch for more than a sprint we easily run the risk of having out of sync migrations and merge conflicts that would slow down development time and cause frustration. Out of sync migrations can also cause technical issues on sandboxes as well, which further adds to development frustration.

**Option 3:** Feature flags
Feature flags are free, allow us to implement thigns over multiple sprints, and some libar

Waffle feature flag libary


**Option 3a:** Feature flags with waffle
The Waffle feature flag library is a highly reccomended django libary for handling large features. It has clear documentation on how to turn on feature flags for user groups as this is one of the main problems it attempts to solve. It also provides Samples which can turn on flags for a certain percent of users and Switches which can be used to hollistically turn features on and off. The reviews from those who used it were highly favorable, some even mentioning how it beat out competitors like gargoyl. It's also comaptible with django admin, providing a quick way to add the view of the flags in django admin so any user with admin access can modify flags for their sandbox.


**Option 3b:** Feature flags with gargoyl
Another feature flag libary with django, but with more forks of the libary, less consitent maintanence and reviews saying it wasn't as easy to work with as waffle. The reviews and less robust documentation were immediatly huge cons to this as an option

**Option 3c:** Paid feature flag system with github integration- LaunchDarkly
LaunchDarkly is a Fedramp'd solution with excellent reviews for controlling feature flags straight from github to promote any team member to be in easy control of setting feature flags. However, the big con to this was that it would be a paid solution and would take time to procure thus slowing down our ability to start on these large features. 



## Decision



## Consequences


