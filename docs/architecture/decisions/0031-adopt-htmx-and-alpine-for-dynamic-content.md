# 31. Adopt htmx and Alpine.js for Frontend Interactions

Date: 2026-04-15

## Status

[change when approved]

## Context

The Django Template Library (DTL) is great at creating forms but not so great at handling complex user interactions like dynamic form updates, hidden elements, etc. We have been using DTL to load JS scripts written in vanilla JavaScript to listen to user generated events (see [Server Side Rendering ADR](https://github.com/cisagov/manage.get.gov/blob/main/docs/architecture/decisions/0008-server-side-rendering.md) for additional context about why this decision was made). 


As we have grown, we have leveraged AJAX (see [AJAX for Dynamic Content ADR](https://github.com/cisagov/manage.get.gov/blob/main/docs/architecture/decisions/0027-ajax-for-dynamic-content.md)) to create a more dynamic SPA-like application. This allowed us to incrementally enhance Django’s server-rendered pages without a significant refactor. However, as we introduce more dynamic FE features, manually implementing them using JS has become unsustainable. We are looking into new solutions to scale our FE with less code complexity.

@lizpearl worked on initial [FE investigation](https://docs.google.com/document/d/1IqxbxwMss2CmocbVsdk8_BV9otaHd-Wl16R9pVIoInc/edit?tab=t.0) to explore options using htmx, React, and at-the-time status quo of DTL and JS.

## Options

### 1. React
**✅ Pros:**
+ Familiar to some team members
+ Larger community to reference for support

**❌ Cons:**
- Takes longer to write components and refactor FE
- Steeper pattern establishment cost. May be costly to refactor if we want to separate from initial patterns (i.e., if we want to split app into microservices)
- Requires JSON APIs (which we don’t currently use)

### 2. htmx + Alpine.js + JS
Use a combination of libraries to handle FE changes in response to a server-side request (htmx), simpler client-side FE changes that can be handled through state management (Alpine.js), and any additional FE changes (JS)

[#3868: htmx discovery PR](https://github.com/cisagov/manage.get.gov/pull/4284) demonstrates current dynamic FE content that we can refactor using htmx with more minimal code.

**✅ Pros:**
+ Lower learning curve than React
+ Rendering server-side avoids the complexity of client-side state management
+ Faster implementation time than DTL and JS for new features 
+ Django compatible. Django requests already return an HTML response, and htmx updates FE using a server-side request and its response. htmx offers the flexibility for our Django requests to return HTML snippets instead of full pages.


**❌ Cons:**
- Due to our project's CSP settings, we must use Alpine's more limited [CSP build](https://alpinejs.dev/advanced/csp).
- Using two libraries may introduce some complexity, however small
- Both htmx and Alpine have smaller support communities than React

## Decision
(#2) Use htmx, Alpine.js, and JS to introduce (and later refactor) dynamic FE features. 

- Use htmx for dynamic FE content in response to a server side request (e.g., API calls).
   - **Example:** Submit a form to create an object in the database, then display that object as a table row on the same page - see [#4429: Refactor DNS records page to HTMX](https://github.com/cisagov/manage.get.gov/pull/4602).
- Use Alpine for simple dynamic content that does not require a server side network request (e.g., showing/hiding an element).
   - **Example:** Toggling visibility of certain HTML to show/hide content - see [#4400: Toggle DNS add record form visibility](https://github.com/cisagov/manage.get.gov/pull/4427). 
- Use JS for anything edge case FE interactions, namely Alpine’s more complex events blocked by our CSP policy
   - **Example:** Displaying different form labels based on another field's dropdown - see [#4408: AAAA record form PR](https://github.com/cisagov/manage.get.gov/pull/4696).

Combining htmx + Alpine.js is a common solution to introduce dynamic FE content to Django projects. Alpine allows us to create dynamic content when depending on a server-side request is unnecessary/excessive. The combination of htmx + Alpine also benefits from a larger support community compared to other solutions like JS + AJAX.

htmx + Alpine.js also does not interfere with future implementations of a Coded Design Library.