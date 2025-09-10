**Below is a step by step guide for generating emails (of each type) in our application. These instructions are UI facing, with the assumption that the user has analyst (or above) permissions.**

## Domain Invitation
- Starting Location: Home page
- Workflow: (Domains Table) Manage domain
- Workflow Step: Click "Manage" -> Click "Domain managers" -> Click "Add a domain manager" -> (enter email) -> Click "Add user"
- [Email Content](https://github.com/cisagov/manage.get.gov/blob/main/src/registrar/templates/emails/domain_invitation.txt)

### Domain Invitation Subject
- Notes: Subject line of the "Domain Invitation" email
- [Email Content](https://github.com/cisagov/manage.get.gov/blob/main/src/registrar/templates/emails/domain_invitation_subject.txt)

## Domain Request Withdrawn
- Starting Location: Home page
- Workflow: (Domain requests Table) Manage domain
- Workflow Step: Click "Manage" -> Click "Withdraw request" -> (confirmation prompt) -> Click "Withdraw request" (inside prompt)
- Notes: You can also do this through Django Admin by switching a domain of status "submitted" to "withdrawn", but you need to be the requester.
- [Email Content](https://github.com/cisagov/manage.get.gov/blob/main/src/registrar/templates/emails/domain_request_withdrawn.txt)

### Domain Request Withdrawn Subject
- Notes: Subject line of the "Domain Request Withdrawn" email
- [Email Content](https://github.com/cisagov/manage.get.gov/blob/main/src/registrar/templates/emails/domain_request_withdrawn_subject.txt)

## Status Change Approved
- Starting Location: Django Admin
- Workflow: Analyst Admin
- Workflow Step: Click "domain requests" -> Click a domain request in a status of "submitted", "In review", "rejected", or "ineligible" -> Click status dropdown -> (select "approved") -> click "Save"
- Notes: Note that this will send an email to the requester. To test this with your own email, you need to create a domain request, then set the status to "approved". This will send you an email.
- [Email Content](https://github.com/cisagov/manage.get.gov/blob/main/src/registrar/templates/emails/status_change_approved.txt)

### Status Change Approved Subject
- Notes: This is the subject line of the "Status Change Approved" email
- [Email Content](https://github.com/cisagov/manage.get.gov/blob/main/src/registrar/templates/emails/status_change_approved_subject.txt)

## Status Change Rejected
- Starting Location: Django Admin
- Workflow: Analyst Admin
- Workflow Step: Click "domain requests" -> Click a domain request in a status of "In review", or "approved" -> Click status dropdown -> (select "rejected") -> click "Save"
- Notes: Note that this will send an email to the requester. To test this with your own email, you need to create a domain request, then set the status to "in review" (and click save). Then, go back to the same application and set the status to "rejected". This will send you an email.
- [Email Content](https://github.com/cisagov/manage.get.gov/blob/main/src/registrar/templates/emails/status_change_rejected.txt)

### Status Change Rejected Subject
- Notes: Subject line of the "Status Change Rejected" email
- [Email Content](https://github.com/cisagov/manage.get.gov/blob/main/src/registrar/templates/emails/status_change_rejected_subject.txt)

## Submission Confirmation
- Starting Location: Home Page
- Workflow: Start domain request
- Workflow Step: Click "Start a new domain request" -> (fill out the form) -> On the last step ("Review and submit your domain request "), click "Submit your domain request"
- Notes: Note that this will send an email to the requester.
- [Email Content](https://github.com/cisagov/manage.get.gov/blob/main/src/registrar/templates/emails/submission_confirmation.txt)

### Submission Confirmation Subject
- Notes: This is the subject line of the "Submission Confirmation Subject" email
- [Email Content](https://github.com/cisagov/manage.get.gov/blob/main/src/registrar/templates/emails/submission_confirmation_subject.txt)

## Transition Domain Invitation
- Notes: This email is generated during the migration process, meaning that there is no using-facing method to receive this email. This email will be sent out when the following conditions are true: a) The domain exists in the data that Verisign sent us, b) the transition domain script ran successfully, and c) invitations are sent out
- [Email Content](https://github.com/cisagov/manage.get.gov/blob/main/src/registrar/templates/emails/transition_domain_invitation.txt)

### Transition Domain Invitation Subject
- Notes: This is the subject line of the "Transition Domain Invitation" email
- [Email Content](https://github.com/cisagov/manage.get.gov/blob/main/src/registrar/templates/emails/transition_domain_invitation_subject.txt)

