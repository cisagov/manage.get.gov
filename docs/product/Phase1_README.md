# A new .gov system: Phase 1
Purpose: Summarize the priorities for 18F and CISA in pursuing an initial build of a new .gov registrar.
**The below was agreed upon on 08/04/2022**

## Goals for Phase 1
**Primary Goal:** Replicate the necessary core functionality in a new system
**Secondary Goal:** Reduce the CISA admin burden while maintaining high security standards

Deprioritized for later:
* Make getting a .gov domain as easy as getting a .com or .us 
* Help more government entities set up and maintain their .gov site and infrastructure
* Build awareness and credibility of .gov domains

## Milestones
_To be prioritized and posted_

## Considerations and Tradeoffs
### Success for Phase 1 is...
* A new system that 
  * Can respond to user needs for all long term goals
  * Can reduce the number of actors or decisions in a successful flow
  * Upholds a security review process for getting a .gov domain
  * Meets code and accessibility standards + open source policy
  * Lays the foundation for a “a simple and secure registration process that works to ensure that domains are registered and maintained only by authorized individuals (Dotgov Act)”
* Supporting 1-2 registrant and admin flows with limited improvement and automation, based on value and complexity
* Has or is ready for an ATO
* Coordinating and navigating with procurement processes (RFPs and current vendor agreement) 

### Risks 
* App may be supported by a combination of manual work and automation, not fully automated
* Scope creep – we build a system that can’t be ATO’d prior to June or Nov 2023
* We build out a narrow slice of the system, which may be insufficient for all registrant and administrative use cases
* We wouldn’t be intentionally and directly focused on or prioritizing improving the registrant / admin experience 

### Example User Stories (to be prioritized)
* As a potential registrant, I want to learn what I should know about .gov so I can build support inside my organization to get a .gov domain.
* As a registrant, I need the registrar to have strong user authentication so that sensitive domain- or account-impacting actions take place post-authentication.
* As a program lead, I need to ensure that issued domains are from authentic, eligible organizations and requested by someone with authority so that domains are only given to bona fide US-based government organizations.
* As a program lead, I need to run queries on .gov data to ensure alignment with program, agency, and Congressional reporting requirements.
* As a program lead, I want to be able to send messages to individuals, groups, or all registrants so they are aware of important information: status emails (system downtime, etc.) to updates to status of an application. (PENDING, APPROVED, etc.).
