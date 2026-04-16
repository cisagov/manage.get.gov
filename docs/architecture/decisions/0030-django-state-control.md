# 30. Django state control after upgrading to Django 5.2

Date: 2026-04-01

## Status

Proposed

## Context

The Django 5.2 upgrade no longer supports the `django-fsm` library, it is both archived and no longer maintained. A replacement is required to continue enforcing finite state machine (FSM) transitions on four models: `Domain`, `DomainRequest`, `DomainInvitation`, and `PortfolioInvitation`.

The project has a strong preference for state security: transitions should be enforced in code, and direct manipulation of state fields should be prevented wherever possible. The two main candidates evaluated are `django-fsm-2` (a community fork of the original library) and `viewflow` (an actively maintained Django workflow and FSM framework).

## Decision

(#1) Use `django-fsm-2`

The library is a direct drop-in replacement for the archived `django-fsm`, is already integrated into the project, and provides the same class of state protection as viewflow. The license, migration cost, and design fit all favor staying with django-fsm-2.

## Considered Options

### 1. django-fsm-2

This would mean replacing the `django-fsm` import with a `django-fsm-2` import and adopting that library as a dependency. `Django-fsm-2` is a community-maintained fork of the original `django-fsm`, transferred to and maintained under [django-commons](https://github.com/django-commons).
In this option, the state field is a FSMfield and transition logic is on the model.

#### Advantages

+ Simply requires replacing the import in the pipfile-zero migration cost, same import path (`from django_fsm import FSMField, transition`)
+ Actively maintained by django-commons; supports Django 4.2–6.0 and Python 3.10–3.14
+ Pre/post transition Django signals for audit logging
+ Lightweight, just an FSM, no extra concepts or dependencies
+ `TransitionNotAllowed` raised on invalid state transitions, matches the error in `django-fsm` in the same scenario
+ MIT license — permissive, no copyleft obligations, perfect given this is an opensource project
+ `protected=True` prevents direct Python-level attribute assignment (`obj.state = 'value'` raises `AttributeError`); `protected=False` remains available for intentional admin overrides ( `DomainRequest.status` uses this)
+ Transition conditions and permission gating built in
+ `ConcurrentTransitionMixin` for optimistic locking against race conditions
+ `FSMAdminMixin` renders transition buttons in Django admin automatically (we may not use this though)

#### Disadvantages

- Fork of an archived project — long-term health depends on the django-commons community staying active
- Smaller contributor pool than django-fsm
- Does not prevent ORM-level bypasses: `Model.objects.filter(...).update(status='value')` still makes changes, no protection at that level as there wasn't protection against this with `django-fsm`
- `protected=False` is an available flag that can override the django-fsm-2 protections, however this too existed in django-fsm. Continues the same potential of misuse.


### 2. viewflow FSM

Adopt viewflow and add it as a dependency, reworking the code to be compatible with it's fsm implementation. [Viewflow](https://viewflow.io) is more than just an FSM it also provides "BPMN-style workflows", "process orchestration,"  and more, meant to be used for complex system workflows.

In this option, the state field is a regular char field using enums (not an FSMfield) and transition logic is in a seperate flow class (not the model).

#### Advantages

+ Actively maintained with a wide audience (2.9k GitHub stars, 416 forks, 365 dependent projects); with code commits as recent as Jan 2026
+ Supports Django 4.2–6.0
+ Uses Python enums for state definitions
+ Always enforces protected state at the Python descriptor level, meaning there's no ability to add `protected=False` and override functionality
+ Part of a larger system with a complex BPMN-style workflow orchestration is available if needed in the future
+ Good official documentation at [docs.viewflow.io](https://docs.viewflow.io/overview/index.html)

#### Disadvantages

- No new releases since april of 2024
- **AGPL-3.0 license** — the strongest copyleft license. While this project is open-source, AGPL liscense usually means the dependent code base (this project), must also distribute under an AGPL license. 
- Does **not** prevent ORM-level bypasses: `queryset.update(state='value')` still works, similiar  fundamental limitation as `django-fsm-2`
- Direct model manipulation to change the state is allowed (where as `django-fsm` & `django-fsm-2` will give a `transitionNotAllowed` error)
- Requires a complete rewrite of all FSM field definitions, transitions, conditions, and permission logic across four models (domain.py, domain_request.py, domain_invitation.py, and portfolio_invitation.py). Plus, flow files for each model, and rewriting about 52 unit tests. This is asignificant refactor with high risk for no security or feature improvement
- The `protected=False` pattern (intentionally used on `DomainRequest` for admin override flows) has no clean equivalent — viewflow always blocks direct assignment, forcing a different design pattern
- Larger dependency footprint; pulls in workflow and BPMN machinery that is not needed (bloat)
- django-admin mixin is only available in "Pro" version
- Commercial "Pro" version could suggest open-source features may be deprioritized relative to paid offerings over time.
