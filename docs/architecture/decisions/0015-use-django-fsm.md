# 15. Use Django-FSM library for domain request state

Date: 2022-11-03

## Status

Accepted

## Context

The applications that registrants submit for domains move through a variety of
different states or stages as they are processed by CISA staff.  Traditionally,
there would be a “domain request” data model with a “status” field. The
rules in the application code that control what changes are permitted to the
statuses are called “domain logic”.

In a large piece of software, domain logic often spreads around the code base
because while handling a single request like “mark this domain request as
approved”, requirements can be enforced at many different points during the
process.

Finite state machines <https://en.wikipedia.org/wiki/Finite-state_machine> are
a mathematical model where an object can be in exactly one of a fixed set of
states and can change states (or “transition”) according to fixed rules.

## Decision

We will use the django-fsm library to represent the status of our domain
registration applications as a finite state machine. The library allows us to
list what statuses are possible and describe which state transitions are
possible (e.g. Can an approved domain request ever be marked as “in-process”?).

## Consequences

This should help us to keep domain logic localized within each model class. It
should also make it easier to design the workflow stages and translate them
clearly into application code.

There is a possible negative impact that our finite state machine library might
be unfamiliar to developers, but we can mitigate the impact by documenting this
decision and lavishly commenting our business logic and transition methods.

