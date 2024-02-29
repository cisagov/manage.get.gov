# 22. Submit Domain Request User Flow

Date: 2023-07-18

## Status

Accepted

## Context

Historically, the .gov vendor managed initial identity verification and organizational affiliation for users that request a .gov domain. With the new registrar, _any user with a valid Login.gov account_ will be able to make a request. As a primary layer of abuse prevention (i.e., DDoSing the registry program with illegitimate requests), we need a way to stop new users from submitting multiple domain requests before they are known to the .gov registry. In this case, "known" means they have at least one approved domain request or existing domain.

## Considered Options

**Option 1:** Users will not be able to submit any new applications if they have 0 prior approved applications OR prior registered .gov domains. We would add a page alert informing the user that they cannot submit their application because they have a domain request in one of these "3" statuses (Submitted, In Review or Action Needed). They would still be able to create and edit new applications, just not submit them. The benefits of this option are that it would allow users to have multiple applications essentially in "draft mode" that are queued up and ready for submission after they are permitted to submit.

**Option 2:** Users will not be able to submit any new applications if they have 0 prior approved applications OR prior registered .gov domains. Additionally, we would remove the ability to edit any application with the started/withdrawn/rejected status, or start a new application. The benefit of this option is that a user would not be able to begin an action (submitting a domain request) that they are not allowed to complete.

## Decision

We have decided to go with option 1. New users of the registrar will need to have at least one approved application OR prior registered .gov domain in order to submit another application. We chose this option because we would like to allow users be able to work on applications, even if they are unable to submit them. 

A [user flow diagram](https://miro.com/app/board/uXjVM3jz3Bs=/?share_link_id=875307531981) demonstrates our decision.
