---
name: Developer Onboarding
about: Onboarding steps for developers.
title: 'Developer Onboarding: GH_HANDLE'
labels: dev, onboarding
assignees: loganmeetsworld

---

# Developer Onboarding

Onboardee: _GH handle of person being onboarded_
Onboarder: _GH handle of onboard buddy_ 

## Installation

There are several tools we use locally that you will need to have.
- [ ] [Install the cf CLI v7](https://docs.cloudfoundry.org/cf-cli/install-go-cli.html#pkg-mac) for the ability to deploy 
- [ ] Make sure you have `gpg` >2.1.7. Run `gpg --version` to check.
- [ ] Install the [Github CLI](https://cli.github.com/)

## Access

- [ ] [Create a cloud.gov account](https://cloud.gov/docs/getting-started/accounts/)
- [ ] Have an admin add you to the CISA Github organization and Dotgov Team.
- [ ] Ensure you can login to your cloud.gov account via the CLI
```
cf login -a api.fr.cloud.gov  --sso
```
- [ ] Have an admin add you to cloud.gov org and relevant spaces as a SpaceDeveloper
```cf set-space-role cloud.account@email.gov ORG SPACE SpaceDeveloper
```
- [ ] Add to our login.gov sandbox team (`.gov registrar poc`) via the [dashboard](https://dashboard.int.identitysandbox.gov/)
- [ ] Setup [commit signing in Github](#setting-up-commit-signing) and with git locally.


## Documents to Review

- [ ] [Team Charter](https://docs.google.com/document/d/1xhMKlW8bMcxyF7ipsOYxw1SQYVi-lWPkcDHSUS6miNg/edit), in particular our Github Policy
- [ ] [Architecture Decision Records](docs/architecture/decisions)
- [ ] [Github Policy](CONTRIBUTING.md)


## Setting up commit signing

Follow the instructions [here](https://docs.github.com/en/authentication/managing-commit-signature-verification/generating-a-new-gpg-key) to generate a new GPG key and add it to your GPG keys on Github.

Configure your key locally: 

```bash
git config --global commit.gpgsign true
git config --global user.signingkey <YOUR KEY>
```

Where your key is the thing you generated to run the command

```bash
gpg --armor --export <YOUR KEY>
```

when setting up your key in Github.

Now test commit signing is working by checking out a branch (`yourname/test-commit-signing`) and making some small change to a file. Commit the change (it should prompt you for your GPG credential) and push it to Github. Look on Github at your branch and ensure the commit is `verified`.
