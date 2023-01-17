---
name: Developer Onboarding
about: Onboarding steps for developers.
title: 'Developer Onboarding: GH_HANDLE'
labels: dev, onboarding
assignees: loganmeetsworld

---

# Developer Onboarding

- Onboardee: _GH handle of person being onboarded_
- Onboarder: _GH handle of onboard buddy_

## Installation

There are several tools we use locally that you will need to have.
- [ ] [Install the cf CLI v7](https://docs.cloudfoundry.org/cf-cli/install-go-cli.html#pkg-mac) for the ability to deploy
- [ ] Make sure you have `gpg` >2.1.7. Run `gpg --version` to check.
- [ ] Install the [Github CLI](https://cli.github.com/)

## Access

### Steps for the onboardee
- [ ] [Create a cloud.gov account](https://cloud.gov/docs/getting-started/accounts/)
- [ ] Have an admin add you to the CISA Github organization and Dotgov Team.
- [ ] Ensure you can login to your cloud.gov account via the CLI
```bash
cf login -a api.fr.cloud.gov  --sso
```
- [ ] Have an admin add you to cloud.gov org and set up your [sandbox developer space](#setting-up-developer-sandbox). Ensure you can deploy to your sandbox space.
- [ ] Have an admin add you to our login.gov sandbox team (`.gov registrar poc`) via the [dashboard](https://dashboard.int.identitysandbox.gov/).

 **Note:** As mentioned in the [Login documentation](https://developers.login.gov/testing/), the sandbox Login account is different account from your regular, production Login account. If you have not created a Login account for the sandbox before, you will need to create a new account first.
- [ ] Setup [commit signing in Github](#setting-up-commit-signing) and with git locally.

### Steps for the onboarder
- [ ] Add the onboardee to cloud.gov org (cisa-getgov-prototyping) 
- [ ] Setup a [developer specific space for the new developer](#setting-up-developer-sandbox)
- [ ] Add the onboardee to our login.gov sandbox team (`.gov registrar poc`) via the [dashboard](https://dashboard.int.identitysandbox.gov/)


## Documents to Review

- [ ] [Team Charter](https://docs.google.com/document/d/1xhMKlW8bMcxyF7ipsOYxw1SQYVi-lWPkcDHSUS6miNg/edit), in particular our Github Policy
- [ ] [Architecture Decision Records](https://github.com/cisagov/dotgov/tree/main/docs/architecture/decisions)
- [ ] [Contributing Policy](https://github.com/cisagov/dotgov/tree/main/CONTRIBUTING.md)


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

**Note:** if you are on a mac and not able to successfully create a signed commit, getting the following error:
```zsh
error: gpg failed to sign the data
fatal: failed to write commit object
```
You may need to add these two lines to your shell's rc file (e.g. `.bashrc` or `.zshrc`)
```zsh
GPG_TTY=$(tty)
export GPG_TTY
```

## Setting up developer sandbox

We have two types of environments: stable, and sandbox. Stable gets deployed via tagged release every sprint, and developer sandboxes are given to get.gov developers to mess around in a production-like environment without disrupting stable. Each sandbox is namespaced and will automatically be deployed too when the appropriate branch syntax is used for that space in an open pull request. There are several things you need to setup to make the sandbox work for a developer. 

TKTK: Actual steps for setting up a new developer sandbox automation.
