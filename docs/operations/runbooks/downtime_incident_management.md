# Downtime & Incident Management Runbook

For the .gov registry and registrar, an incident is defined as an event that impacts the confidentiality, availability, or integrity of the registrar that isn’t expected. Some examples include:

* When get.gov and/or manage.get.gov are completely offline/unavailable to users;  
* The application is returning critical errors unexpectedly; or  
* Data is able to be accessed by someone other than the intended audience.

This runbook is primarily designed to cover our response for incidents that are a result of critical bugs in the .gov codebase or an outage with one of our providers. However, since the root cause of a problem may not be immediately evident, following these procedures will assist in identifying and mitigating the issue, even if that source is an intentional, malign actor.

Certain types of incidents, such as when the root cause is determined to be malware, ransomware, denial of service, and the like, may require additional measures and assessment, including coordination with CISA's incident response or privacy offices. Those are not detailed in this runbook.

## Availability and developer support

The .gov team's availability spans normal business hours for CONUS. The team also includes contract developers. 

For incident management purposes, the following should be noted:

* Engineers who are online should join the incident-related huddle as soon as practical. Engineers who are off may be pinged or invited to join, but are not obligated to assist.

## Something’s wrong\! Now what?

1. Announce incident using **@here** in \#dotgov-announce Slack channel  
   1. Anyone can begin an incident, including new team members and non-developers.  
2. If no developers have acknowledged the incident announcement within 10 minutes, the person who called the incident should initiate a Slack Huddle call in DMs with individual engineers.  
   1. If there are no responses, escalate to a phone call, utilizing the [.gov emergency contact list document](https://docs.google.com/document/d/1k4r-1MNCfW8EXSXa-tqJQzOvJxQv0ARvHnOjjAH0LII/edit?tab=t.0#heading=h.jzudhpsxyys2)  
3. Start a huddle in \#dotgov-redalert to begin incident response  
    * Identify **incident lead**, who will coordinate across *engineers and team* for necessary actions.  
    * Identify any required participants for incident response (ie, if the incident requires specific engineers or leads because of its scope)  
    * Designate **communication lead**  
      * This will typically not be an engineer, but someone who will assist in drafting banner content; communicating outside of the .gov team; and updating the team and the incident document.  
    * *Communication lead* creates a copy of our incident response template Google Doc and begins comms as detailed in the “Communications” section.  
      * Template document to copy: : [0 - Template - Incident Dashboard + Report](https://docs.google.com/document/d/1cSRso-d71EafJKt8_3RXj37Oz_lPpM0n05leiyyHiLc/edit?usp=drive_link)  
      * Location: [incidents \- .gov \- Google Drive](https://drive.google.com/drive/folders/1LPVICVpI4Xb5KGdrNkSwhX2OAJ6hYTyu) folder  
      * Name: `YYYY-MM-DD \- Incident \- {short description}`
4. **Troubleshoot, patch, or resolve issue**   
5. Make updates to the incident report document and status information on the Dashboard tab of the document  
6. Schedule a team retrospective, typically within 24 hours of resolution  
   1. Review “Incident Report” tab for a list of questions and areas to visit during the retrospective to create a complete incident report  
7. Update incident report status in the incident document to indicate completion.

### Communications

#### As soon as possible once an incident is called

1. Identify the issue sufficiently to have 1-3 sentences explaining what’s happening, to provide the following notifications:  
   1. CISA incident response team  
      1. Should be communicated by a federal employee, share what we know, and indicate we’ll offer regular updates as we can.  
   2. .gov Analysts (via internal Teams channel)  
      1. Be sure to include a description of what the Analysts and/or users may see, so they can triage any incoming questions  
2. Determine if an [alert banner](https://designsystem.digital.gov/components/alert/) should be added to get.gov and/or manage.get.gov.   
   1. Draft content, get review and approval from Program team  
   2. Add banner(s)  
      1. *For get.gov*: uncomment the desired banner in [header.html](https://github.com/cisagov/get.gov/blob/main/_includes/header.html) and edit that banner’s content in [\_includes](https://github.com/cisagov/get.gov/tree/main/_includes). ([Example](https://github.com/cisagov/get.gov/pull/370/files))  
      2. *For manage.get.gov*: update [base.html](https://github.com/cisagov/manage.get.gov/blob/main/src/registrar/templates/base.html#L78) and then edit that banner’s content in [includes](https://github.com/cisagov/manage.get.gov/tree/main/src/registrar/templates/includes). ([Example](https://github.com/cisagov/manage.get.gov/pull/3459/files#diff-24a19f8e02cf98f078ebc9fdcd0a18db8b32c29a52f5f366caf7b6a4eb083f71))  
3. Program Manager and/or program team should determine if additional communications are needed within CISA, such as to CB, CSD, or CISA leadership

#### Ongoing

1. Approximately \~hourly, or if significant new information is determined, make updates:  
   1. Incident response document Dashboard tab  
   2. IRT   
   3. Analysts  
   4. Banners, if appropriate  
   5. Inside CB, CSD, CISA, as appropriate  
   6. Consider if it is appropriate to directly notify users via emails  
2. Continue to monitor incident actions and communications to add to the timeline in the incident response document.

#### On incident resolution

1. Update the following to provide notice that the incident is resolved  
   1. In \#dotgov-announce Slack channel  
   2. IRT  
   3. Analysts  
   4. Banner(s) removed  
   5. Any others that were notified inside, outside CISA  
2. Anyone on the .gov team who participated in the incident should, as soon as practicable, add timeline events, logs, or other information about the incident to the incident report document, while the information is fresh.  
3. If the issue is resolved, but cause unknown, developers should investigate as the highest priority task.  
4. Program team or incident lead will schedule an hour-long retrospective session for the team. The retro is an opportunity to do the following:  
   1. Review the timeline of the incident and ensure it’s accurate  
   2. Identify anything that contributed to the incident \- not just causes, but conditions that worked together to create the incident, and escalate to the severity it was  
   3. Identify anything that helped mitigate impacts of the incident
   4. Review what we learned, and any risks that were uncovered  
   5. Propose and agree on follow-up actions, including necessary GitHub issues, and owners for completion of follow-up activities

After retrospective, the program team coordinates to finalize the Incident Report using the template in the incident report document. The incident report is a consolidated narrative, timeline, and assessment of the incident to share internally. The program team will also determine if any external notifications are warranted, such as emails to users, published to get.gov, etc.