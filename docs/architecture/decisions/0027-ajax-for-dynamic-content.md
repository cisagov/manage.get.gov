# 27. Ajax for Dynamic Content

Date: 2024-05-22 (back dated)

## Status

Approved

## Context

When we decided to implement server-side rendering ([ADR#8 - Server-Side rendering](./0008-server-side-rendering.md)), we identified a potential risk: users and stakeholders might expect increasingly interactive experiences similar to those found in single-page applications (SPAs). Modern JavaScript frameworks such as React, Angular, and Vue enable rich interactivity by allowing applications to update portions of the page dynamically—often without requiring a full-page reload. These frameworks abstract AJAX and DOM manipulation, creating a high-level interface between JavaScript, HTML, and the browser.

Our decision to use Django for server-rendered pages allowed us to deliver an MVP quickly and facilitated easy onboarding for new developers. However, the anticipated risk materialized, and stakeholders now expect a more seamless, SPA-like experience.

We already leverage vanilla JavaScript for interactive components throughout the application. These implementations are neatly contained within Immediately Invoked Function Expressions (IIFEs) and are designed to extend specific components without interfering with Django’s server-rendered structure.

However, new components that require features like pagination, search, and filtering demand a more responsive, real-time user experience. This prompted an exploration of possible solutions.

## Considered Options

**Option 1:** Migrate to a Full SPA with Django as a Backend API
This approach involves refactoring Django into a backend-only service and adopting a modern JavaScript framework for the frontend.

✅ Pros:
- Future-proof solution that aligns with modern web development practices.
- Enables highly interactive and dynamic UI.
- Clean separation of concerns between frontend and backend.

❌ Cons:
- Requires significant investment in development and infrastructure changes.
- Major refactoring effort, delaying feature delivery.
- Increased complexity for testing and deployment.

This approach was deemed too costly in terms of both time and resources.

---

**Option 2:** Adopt a Modern JS Framework for Select Parts of the Application
Instead of a full migration, this approach involves integrating a modern JavaScript framework (e.g., React or Vue) only in areas that require high interactivity.

✅ Pros:
- Avoids a complete rewrite, allowing incremental improvements.
- More flexibility in choosing the level of interactivity per feature.

❌ Cons:
- Introduces multiple frontend paradigms, increasing developer onboarding complexity.
- Requires new deployment and build infrastructure.
- Creates long-term technical debt if legacy Django templates and new JS-driven components coexist indefinitely.

This approach would still introduce diverging implementation stacks, leading to long-term maintenance challenges.

---

**Option 3:** Use a Lightweight JavaScript Framework (e.g., HTMX, HTMZ)
Instead of React or Vue, this approach involves using a minimal JavaScript framework like HTMX or HTMZ to enhance interactivity while preserving Django’s server-rendered structure.

✅ Pros:
- Reduces the need for a full rewrite.
- Keeps Django templates largely intact.
- Minimizes complexity compared to React or Vue.

❌ Cons:
- Limited community support and long-term viability concerns.
- Still introduces new technology and learning curves.
- Unclear whether it fully meets our interactivity needs.

Ultimately, we determined that the benefits did not outweigh the potential downsides.

---

**Option 4:** Extend Vanilla JavaScript with AJAX (Selected Option)
This approach involves incrementally enhancing Django’s server-rendered pages with AJAX while maintaining our existing architecture.

✅ Pros:
Avoids expensive refactors and new dependencies.
- Fully customized to our existing codebase.
- Keeps Django templates intact while allowing dynamic updates.
- No need for additional build tools or frontend frameworks.

❌ Cons:
- Requires designing our own structured approach to AJAX.
- Testing and maintainability must be carefully considered.

This approach aligns with our existing architecture and skill set while meeting stakeholder demands for interactivity.

## Decision
We chose Option 4: Extending our use of vanilla JavaScript with AJAX.

## Consequences
1. Ownership of Solution
 - We fully control the implementation without external dependencies.

2. Maintainability
 - Our AJAX implementation will follow an object-oriented approach, with a base class for components requiring pagination, search, and filtering.

3. Backend Considerations
 - Views handling AJAX responses will be explicitly designated as JSON views.

4. Scalability
 - While this approach works now, we may need to reassess in the future if interactivity demands continue to grow.

This decision allows us to enhance the application's responsiveness without disrupting existing architecture or delaying feature development.
