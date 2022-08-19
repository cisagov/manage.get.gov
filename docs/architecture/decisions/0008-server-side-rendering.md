# 8. Server Side Rendering

Date: 2022-08-16

## Status

Accepted

## Context

In deciding how content would be delivered to the end user, we held a meeting with Engineering and Design ~and the mayor of Igorville~ [^1] and consulted the [18F Engineering Practices Guide](https://engineering.18f.gov/web-architecture/).

The two major options considered were 1) a single page application, developed with a JavaScript framework such as React, perhaps served from its own Node-based server or a static file host such as Federalist; or 2) traditional server rendered HTML pages, delivered by Django, accompanied by a small amount of JavaScript and CSS.

## Decision

To use server-side rendering performed by Django.

## Consequences

The positive aspects of this include: easier state management, fewer bugs caused by stale cache data, easier 508 compliance for disabled users, better maintainability for future developers due to fewer dependencies and a shallower learning curve, and better cross browser compatibility.

The risks to this approach are given by the frontend lead on a sister 18F project: a less well-developed API since this approach does not require an API upfront, users/stakeholders attempting to request ever increasing levels of interactivity, and familiarity with vanilla.js has waned over the years.

[^1]: Inside joke. To obtain access to the registrant flow, a member of our team signed up for .gov using the fictitious town of Igorville.
