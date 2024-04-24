# Downtime Incident Management Runbook

 Our team has agreed upon steps for handling incidents that cause our site to go offline or become unusable for users. For this document, an incident refers to one in which manage.get.gov is offline or displaying error 400/500 HTTP errors on all pages. However, for this document to apply the cause of the problem must be a critical bug in our code or one of our providers having an outage, not to be confused with a cyber security incident. This document should not be used in response to any type of cyber security incident.

## Response management rules

The following set of rules should be followed while an incident is in progress.

- The person who first notices that the site is down is responsible for using @here and notifying in #dotgov-announce that production is down.
  - This applies to any team member, including new team members and non-developers.
- If no engineer has acknowledged the announcement within 10 minutes, whoever discovered the site was down should call each developer via the Slack DM huddle feature. If there is no response, this should escalate to a phone call.
  - When calling, go down the [phone call list](https://docs.google.com/document/d/1k4r-1MNCfW8EXSXa-tqJQzOvJxQv0ARvHnOjjAH0LII/edit) from top to bottom until someone answers who is available to help.
  - If this incident occurs outside of regular working hours, choosing to help is on a volunteer basis, and answering a call doesn't mean an individual is truly available to assist.
- Once an engineer is online, they should immediately start a huddle in the #dotgov-redalert channel to begin troubleshooting.
- All available engineers should join the huddle once they see it.
  - If downtime occurs outside of working hours, team members who are off for the day may still be pinged and called but are not required to join if unavailable to do so.
- Uncomment the [banner on get.gov](https://github.com/cisagov/get.gov/blob/0365d3d34b041cc9353497b2b5f81b6ab7fe75a9/_includes/header.html#L9), so it is transparent to users that we know about the issue on manage.get.gov.
  - Designers or Developers should be able to make this change; if designers are online and can help with this task, that will allow developers to focus on fixing the bug.
- If the issue persists for three hours or more, follow the [instructions for enabling/disabling a redirect to get.gov](https://docs.google.com/document/d/1PiWXpjBzbiKsSYqEo9Rkl72HMytMp7zTte9CI-vvwYw/edit).

## Post Incident

The following checklist should be followed after the site is back up and running.

- [ ] Message in #dotgov-announce with an @here saying the issue is resolved.
- [ ] If the redirect was used, refer to the [instructions for enabling/disabling a redirect to get.gov](https://docs.google.com/document/d/1PiWXpjBzbiKsSYqEo9Rkl72HMytMp7zTte9CI-vvwYw/edit) to turn off this redirect. Double-check in the browser that this redirect is no longer occurring (the change may take a few minutes to take full effect).
- [ ] Remove the [banner on get.gov](https://github.com/cisagov/get.gov/blob/0365d3d34b041cc9353497b2b5f81b6ab7fe75a9/_includes/header.html#L9) by commenting it out.
- [ ] Write up what happened and when; if the cause is already known, write that as well. This is a draft for internal communications and not for any public facing site and can be as simple as using bullet points.
- [ ] If the cause is not known yet, developers should investigate the issue as the highest priority task.
- [ ] As close to the event as possible, such as the next day, perform a team incident retro that is an hour long. The goal of this meeting should be to inform all team members what happened and what is being done now and to collect feedback on what could have been done better. This is where the draft write up of what happened will be useful.
- [ ] After the retro and once the bug is fully identified, an engineer should assist in writing an incident report and may be as detailed as possible for future team members to refer to. That document should be places in the [Incidents folder](https://drive.google.com/drive/folders/1LPVICVpI4Xb5KGdrNkSwhX2OAJ6hYTyu).
- [ ] After creating the document above, the lead engineer make a draft of content that will go in the get.gov Incidents section. This Word document should be shared and reviewed by the product team before a developer adds it to get.gov.
