# Downtime Incident Management Runbook

 Our team has agreed upon steps for handling incidents that cause our site to go offline or become unusable for users. For this document, an incident refers to one in which manage.get.gov is offline or displaying error pages (400-500) and is caused by a critical bug in our code, not to be confused with a security incident. This document should not be used for security incident response.

## Response management rules

The following set of rules should be followed while an incident is in progress.

- The person who first notices that the site is down is responsible for using @here and notifying in #dotgov-announce that production is down
- If no engineer has acknowledged the announcement within 10 minutes, whoever discovered the site was down should call each developer via the Slack DM huddle feature. If there is no response, this should escalate to a phone call.
  - When calling, go down the list phone call list from top to bottom until someone answers
- Once an engineer is online, they should immediately start a huddle in the #dotgov-redalert channel to begin troubleshooting
- **All** available engineers should join the huddle once they see it.
- Uncomment the banner on get.gov, so it is transparent to users that we know about the issue on manage.get.gov
  - Designers or Developers should be able to make this change; if designers are online and can help with this task, that will allow developers to focus on fixing the bug.
- If the problem is not solved within three hours, change the rules on Cloudflare's admin site so that navigating to manage.get.gov redirects users to get.gov. This will help them see the banner on get.gov informing them that this is a known problem

## Post Incident

The following checklist should be followed after the site is back up and running.

- [ ] Turn off the redirect (if used) and verify functionality
- [ ] Remove the banner on get.gov by commenting it out
- [ ] Write up what happened and when. If the cause is already known, write that as well.
- [ ] If the cause is not known yet, developers should investigate the issue as the highest priority task.
- [ ] As close to the event as possible, such as the next day, perform a team incident retro that is an hour long. The goal of this meeting should be to inform all team members what happened and what is being done now and to collect feedback on what could have been done better
