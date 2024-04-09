---
name: Designer Onboarding
about: Onboarding steps for designers.
title: 'Designer Onboarding: GH_HANDLE'
labels: design, onboarding
assignees: katherineosos

---

# Designer Onboarding

- Onboardee: _GH handle of person being onboarded_
- Onboarder: _GH handle of onboard buddy_

Welcome to the .gov team! We're excited to have you here. Please follow the steps below to get everything set up. An onboarding buddy will help grant you access to all the tools and platforms we use. If you haven't been assigned an onboarding buddy, let us know in the #dotgov-disco channel. 

## Onboardee

### Steps for the onboardee
- [ ] Read the [.gov onboarding doc](https://docs.google.com/document/d/1ukbpW4LSqkb_CCt8LWfpehP03qqfyYfvK3Fl21NaEq8/edit?usp=sharing) thoroughly.
- [ ] Accept an invitation to our Slack workspace and fill out your profile.
  - [ ] For our Slack profile names, we usually follow the naming convention of `Firstname Lastname (Org, State, pronouns)`. 
      Example: Katherine Osos (Truss, MN, she/her)
  - [ ] Make sure you have been added to the necessary [channels](https://docs.google.com/document/d/1ukbpW4LSqkb_CCt8LWfpehP03qqfyYfvK3Fl21NaEq8/edit#heading=h.li3lqcygw8ax) and familiarize yourself with them.
- [ ] Create a [Google workspace enterprise account](https://docs.google.com/document/d/1ukbpW4LSqkb_CCt8LWfpehP03qqfyYfvK3Fl21NaEq8/edit?pli=1#heading=h.xowzg9w0qlis) for CISA.
- [ ] Get access to our [Project Folder](https://drive.google.com/drive/folders/1qkoFQBlzXA7axi9CZ_OBhlJqRcqlNfpW?usp=drive_link) on Google Drive.
  - [ ] Explore the folders and docs. Designers interface with the Product Design, Content, and Research folders most often.
- [ ] Make sure you have been invited to our [team meetings](https://docs.google.com/document/d/1ukbpW4LSqkb_CCt8LWfpehP03qqfyYfvK3Fl21NaEq8/edit#heading=h.h62kzew057p1) on Google Meet.
- [ ] Review our [design tools](https://docs.google.com/document/d/1ukbpW4LSqkb_CCt8LWfpehP03qqfyYfvK3Fl21NaEq8/edit?pli=1#heading=h.aprurp3z4gmv).
- [ ] Accept invitation to our [Figma workspace](https://www.figma.com/files/1287135731043703282/team/1299882813146449644).
- [ ] Follow the steps in [Preparing for your sandbox](#preparing-for-your-sandbox) section below.
- [ ] Schedule coffee chats with Design Lead, other designers, scrum master, and product manager ([team directory](https://docs.google.com/document/d/1ukbpW4LSqkb_CCt8LWfpehP03qqfyYfvK3Fl21NaEq8/edit?pli=1#heading=h.1vq6r8e52e9f)).
- [ ] Look over [recommended reading](https://docs.google.com/document/d/1ukbpW4LSqkb_CCt8LWfpehP03qqfyYfvK3Fl21NaEq8/edit?pli=1#heading=h.7ox9ee7v5q5n) and [relevant links](https://docs.google.com/document/d/1ukbpW4LSqkb_CCt8LWfpehP03qqfyYfvK3Fl21NaEq8/edit?pli=1#heading=h.d9pac1gc751t).
- [ ] Fill out your own Personal Operating Manual (POM) on the [team norming board](https://miro.com/app/board/uXjVMxMu1SA=/). Present it on the next team coffee meeting. 
- [ ] FOR FEDERAL EMPLOYEES: Check in with your manager on the CISA onboarding process and getting your PIV card.
- [ ] FOR CONTRACTORS: Check with your manager on your EOD clearance process.
- [ ] OPTIONAL: Request access to our [analytics tools](https://docs.google.com/document/d/1ukbpW4LSqkb_CCt8LWfpehP03qqfyYfvK3Fl21NaEq8/edit?pli=1#heading=h.9q334hs4lbks). 


#### Preparing for your sandbox
- [ ] Create two identity sandbox accounts, this is login.gov’s test environment
  - How to make it:
    - [ ] Navigate to [identity sandbox](https://idp.int.identitysandbox.gov/)
    - [ ] Click create an account
    - [ ] Fill in the information with fake data, though you may choose to use your real name. For the social security field, input a SSN that starts with 666 or 900. Instead of uploading a picture of your ID, you may upload any picture (include a cat meme).
    - [ ] See login.gov’s [developer section](https://developers.login.gov/testing/#testing-identity-proofing) for testing with identity sandbox if you encounter issues.
  - One account should be your preferred work email for the username, the second should be the SAME email address followed by a plus one
    - Ex: bob@dhs.gov for the first login account and bob+1@dhs.gov
    - One account will represent a normal user while the other will be your way of simulating a “analyst”
- [ ] Sandbox: Have an engineer create a sandbox for you (message in #dotgov-dev Slack channel). This will be used to make content updates in the UI.
  - [ ] You will receive a link for Cloud.gov to be added to an organization. Be sure to verify via that link or you may not be able to access any sandbox.
  - [ ] Also ask that they add mock data to that sandbox. This will be helpful for testing various scenarios in the UI.
    - Note: at any point you can add mock data to your sandbox and reset all test data in you sandbox by running the [reset action on github](https://github.com/cisagov/getgov/actions/workflows/reset-db.yaml)
      - Go to the provided link. Click the Run Workflow dropdown
      - Select your sandbox environment (your initials).
      - Then click the green “Run workflow” button
   - [ ] Your sandbox makes the app available online, and everyone should be able to access your sandbox once it is made. See the [sandbox section of the onboarding doc](https://docs.google.com/document/d/1ukbpW4LSqkb_CCt8LWfpehP03qqfyYfvK3Fl21NaEq8/edit#heading=h.cdlfxamcvus5), your sandbox url will be in this format: `https://getgov-<ENV>.app.cloud.gov/` where ENV refers to your initials.
   - [ ] Make sure to check that you can log into your sandbox with the identity sandbox login credentials you made.
- [ ] Request access to /admin (also known as “add to fixtures”)
  - [ ] Follow the steps in the [developer readme for adding yourself to admin](https://github.com/cisagov/getgov/blob/main/docs/developer/README.md#adding-user-to-admin)
    - When you get to the last step about editing the code, you can instead share the ID you found in the previous step with someone on the development team.
- [ ] OPTIONAL: Request an “analyst” account by using your second identity sandbox credential 
  - This account will allow you to see what an analyst sees when they log in to the application
  - Use whichever identity sandbox account you did not use when requesting /admin access and follow the [developer readme for creating an analyst account](https://github.com/cisagov/getgov/blob/main/docs/developer/README.md#adding-an-analyst-to-admin)
    - Just like with /admin, in the last step about editing the code you can instead share the ID you found in the previous step with someone on the development team


### Access
By following the steps, you should have access / been added to the following:
- [ ] The [.gov team](https://github.com/orgs/cisagov/teams/gov) under cisagov on GitHub
- [ ] [Slack](dhscisa.enterprise.slack.com), and have been added to the necessary channels
- [ ] [Google Drive Project folder](https://drive.google.com/drive/folders/1qkoFQBlzXA7axi9CZ_OBhlJqRcqlNfpW?usp=drive_link)
- [ ] [.gov team on Figma](https://www.figma.com/files/1287135731043703282/team/1299882813146449644) (as an editor if you have a license)
- [ ] [Team meetings](https://docs.google.com/document/d/1ukbpW4LSqkb_CCt8LWfpehP03qqfyYfvK3Fl21NaEq8/edit#heading=h.h62kzew057p1)


## Onboarder

### Steps for the onboarder
- [ ] Make sure onboardee is given an invitation to our Slack workspace
- [ ] Add onboardee to dotgov Slack channels
- [ ] Once onboardee has a Google workspace enterprise account, add onboardee to Project Folder as an editor
- [ ] Once onboardee has been granted a Figma license, add them as an editor to the Figma team workspace
- [ ] Add onboardee to our team meetings
- [ ] If applicable, invite onboardee to Google Analytics, Google Search Console, and Search.gov console
