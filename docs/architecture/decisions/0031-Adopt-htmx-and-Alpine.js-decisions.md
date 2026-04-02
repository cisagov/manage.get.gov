# 31. Adopt htmx and Alpine.js for Frontend Interactions

Date: 20XX-XX-XX

## Status

Accepted

## Context

The Django Template Library (DTL) handles form creation well, but complex user interactions have been addressed by loading vanilla Javascript through HTML. 
This JS codebase has grown difficult to organize and maintain. The team evaluated new frontend approaches to reduce code complexity while remaining 
compatible with potential coded design library. Two primary options were considered: htmx and React 

## Reasoning for htmx and Alpine.js

* htmx integrates naturally with Django and DTL -- endpoints can return HTML snippets instead
* Alpine.js fills the gap htmx leaves for client-side behavior, replacing the vanilla JS that had been growing unmanageable
* Together, the two libraries cover the full range of interaction needs without requiring React

## Pros and Cons

+ Lower learning curve than React
+ Rendering on server-side avoids the complexity of client-side state management
+ Faster implementations for new features than DTL and JS

- Both htmx and Alpine have smaller support communities than React
- Two libraries introduces some complexity, however small

## Alternatives Considered

React
* familiar to some team members
* requires JSON APIs
* longer to write components
* steeper pattern establishment cost

htmx alone
* HTMX cannot account for all client-side behavior. Additional library will be required.

DTL + vanilla JS
* ruled out due to poor scalability
* growing complexity

## Tradeoffs and Risks

* htmx doubles down on Django, making a future migration to microservices more difficult
* Alpine restructures JS logic; vanilla JS may still be required in the CSP build

## Consequences

New frontend patterns will be estabilished through designated DNS hosting tickets. An additional ADR may follow
once prototype implementations prove successful. Questions should be directed to Liz