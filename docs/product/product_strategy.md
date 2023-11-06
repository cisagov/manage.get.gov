# .Gov product strategy
Purpose: Clarify our focus for developing a new .gov TLD system and align it to the needs of our users, CISA's mission and standards, and the vision for the .gov program.

# .Gov mission statement

.gov helps U.S.-based government organizations gain public trust by making .gov a well-known, reliable, and secure space online.

## Product vision

CISA intends to create a modern, user-centered, responsive web application to enable .gov registrants to manage their domain’s registration lifecycle, DNS settings, and useful supporting services. The registrar should be the central .gov hub for CISA, supporting registrant management, and tracking technical performance indicators for the TLD. For CISA and registrants, the registrar should help generate insights into the security of an organization’s internet-accessible systems.

## Problem statements
U.S.-based government organizations and publicly controlled entities lack a clear, usable, and efficient way to apply for, register, and manage .gov domains and related infrastructure to build public trust in their online services and communications.

CISA lacks a scalable, efficient, and secure method of managing the .gov TLD program that helps government agencies to build public trust in their online services and communications.

## Objective and key results for .gov

| **Objective**                                                                                                                                                                                 | **Key result**                                                                                                                                                                                  |
|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Growth and use:** Regular growth in the overall number of .gov domains registered, with clear increases in election orgs, major metro areas, and state legislatures/courts                  | - Raw count of registered .gov domains increases <br /> - Number of YoY applications per month increases <br /> - Percent of 100 most populous cities, counties, etc. (per Census data) using .gov domains increases |
| **Data:** The program maintains authoritative contacts at, metadata about, and hostname information for all registered .gov domains, and is able to track that .gov domains are actually used | - Time-to-generate internal reports decreases <br /> - Results of periodic data quality audit show improvements month-over-month                                                                              |
| **User satisfaction:** Getting a .gov domain is as easy and intuitive as possible                                                                                                             | - Completion rate of form improves <br /> - Time from domain request to approval decreases <br /> - Number of domains requiring analyst data changes decreases                                                        |
| **Program reputation and experience:** The .gov program is viewed as trustworthy and responsive                                                                                               | - Response time for inquiries decreases <br /> - Resolution time decreases <br /> - Rate of repeat issues for tickets decreases <br /> - Number of SLTT organizations in Community of Practice increases                                      |

## Bug triage

Bugs on production software need to be documented quickly and triaged to determine if fixes need to be made outside of the normal release cadence. Triage levels will be Critical, High, Medium, and Low to indicate the level of priority for fix, not neccessarily the level of severity. See below for more details

**Critical**- should only be determined by the product owner and means the fix for this critical bug needs to have a quick fix for it created ASAP. This is the only case where a bug fix can be added outside of the normal release cycle and directly onto the stable release.
**High**- Can be determined by product owner or other team member, and indicates this bug is critical enough to warrant being added into the current sprint.
**Medium**- Should be added to a sprint coming up but is not blocking users, or enough users to warrant rushing it into a sprint
**Low**- A minor bug, that could even wait until after the next big launch date to be implemented.

### Steps for Triaging

1. When a bug is found, whether by a developer/designer or from feedback from an end user, a ticket should be made immediately. The actual maker of the ticket can be a member of the product team as needed.
2. This bug ticket immediately gets a priority added Critical/High/Medium/Low, with Critcal requiring the product owner's request.
3. Anything marked as `critical` should be refined immediately and engineering should be notified via Slack that a Critical ticket has been created (if not already notified)
4. All items not marked as `critical` by the product owner, can wait until refinement to be refined and may have their prioirty level changed during that meeting.

### Steps for dealing with Critical Bugs

1. Once the critical bug ticket is refined and the bug is clear, an engineer should be assigned to work on it. (No ticket, no work)
2. At the same point, two other engineers should be assigned to review the PR once it's made. One of the reviewing engineers can be subsititued for a designer if this is a design/content/other user facing bug fix.
3. In the case where the engineering lead is not responsive/ unavailable to assign the ticket immediatley, other engineers should see the public slack message and volunteer as needed. The product team will be backup to make sure someone is assigned or volunteers for the ticket/PR review ASAP.
4. Once done the developer, now needs to make a PR as usual but should tag the assigned PR reviewers in a public slack message stating that the PR is now waiting on their review. These reviewers should drop other tasks in order to review this promptly.
5. See the Making bug fixes on stable during production readme for how to push changes to stable once the PR is approved
