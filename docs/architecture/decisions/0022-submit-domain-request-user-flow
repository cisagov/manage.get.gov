# 22. Submit Domain Request User Flow

Date: 2023-07-18

## Status

Accepted

## Context

Historically, Verisign has managed the identity verification for users who request to apply for a .gov domain. With CISA's new system, any user who creates an account and verifies themselves through Login.gov will be able to request a .gov domain. As another layer of mitigation against abuse of the system, we needed a way to stop new users from submitting multiple domain requests before they are verified by CISA analysts.

## Considered Options

Option 1: Users that don't meet the requirement of having a prior approved application will not be able to submit any new applications. We add a page alert informing the user that they cannot submit their application because they have an application in one of these "3" statuses (Submitted, In Review or Action Needed). They would still be able to create and edit new applications, just not submit them. The benefits of this option are that it would allow users to have multiple applications essentially in "draft mode" that are queued up and ready for submission after they are permitted to submit (after approval of 1 application).

Option 2: Users that don't meet the requirement of having a prior approved application will not be able to submit any new applications. Additionally, we would remove the ability to edit any application with the started/withdrawn/rejected status, or start a new application. The benefit of this option is that a user would not be able to begin an action (submitting an application) that they are not allowed to complete.

## Decision

We have decided to go with option 1. New users of the registrar will need to have at least one approved application OR prior registered .gov domain in order to submit another application. We would like to allow users be able to work on applications, even if they are unable to submit them. [A user flow diagram that demonstrates this logic can be viewed at this link](https://miro.com/app/board/uXjVM3jz3Bs=/?share_link_id=875307531981). 
