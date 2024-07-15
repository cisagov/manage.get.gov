---
name: Developer Onboarding
about: Onboarding steps for new developers joining the .gov team.
title: 'Developer Onboarding: GH_HANDLE'
labels: dev, onboarding
assignees: abroddrick

---

# Developer Onboarding

- Onboardee: _GH handle of person being onboarded_
- Onboarder: _GH handle of onboard buddy_

## Installation

There are several tools we use locally that you will need to have.
- [ ] [Install the cf CLI v7](https://docs.cloudfoundry.org/cf-cli/install-go-cli.html#pkg-mac) for the ability to deploy
  - If you are using Windows, installation information can be found [here](https://github.com/cloudfoundry/cli/wiki/V8-CLI-Installation-Guide#installers-and-compressed-binaries)
  - Alternatively, for Windows, [consider using chocolately](https://community.chocolatey.org/packages/cloudfoundry-cli/7.2.0)
- [ ] Make sure you have `gpg` >2.1.7. Run `gpg --version` to check. If not, [install gnupg](https://formulae.brew.sh/formula/gnupg)
  - Alternatively, you can skip this step and [use ssh keys](#setting-up-commit-signing-with-ssh) instead
- [ ] Install the [Github CLI](https://cli.github.com/)

## Access

### Steps for the onboardee
- [ ] Setup commit signing in Github and with git locally using either [gpg](#setting-up-commit-signing-with-gpg) or [ssh](#setting-up-commit-signing-with-ssh).
- [ ] [Create a cloud.gov account](https://cloud.gov/docs/getting-started/accounts/)
- [ ] Email github@cisa.dhs.gov (cc: Cameron) to add you to the [CISA Github organization](https://github.com/getgov) and [.gov Team](https://github.com/orgs/cisagov/teams/gov).
- [ ] Ensure you can login to your cloud.gov account via the CLI
```bash
cf login -a api.fr.cloud.gov  --sso
```
- [ ] Have an admin add you to cloud.gov org and set up your [sandbox developer space](#setting-up-developer-sandbox). Ensure you can deploy to your sandbox space.
- [ ] Have an admin add you to our login.gov sandbox team (`.gov Registrar`) via the [dashboard](https://dashboard.int.identitysandbox.gov/).

 **Note:** As mentioned in the [Login documentation](https://developers.login.gov/testing/), the sandbox Login account is different account from your regular, production Login account. If you have not created a Login account for the sandbox before, you will need to create a new account first.

- [ ] Optional- add yourself as a codeowner if desired. See the [Developer readme](https://github.com/cisagov/getgov/blob/main/docs/developer/README.md) for how to do this and what it does.

### Steps for the onboarder
- [ ] Add the onboardee to cloud.gov org (cisa-dotgov) 
- [ ] Setup a [developer specific space for the new developer](#setting-up-developer-sandbox)
- [ ] Add the onboardee to our login.gov sandbox team (`.gov Registrar`) via the [dashboard](https://dashboard.int.identitysandbox.gov/)


## Documents to Review

- [ ] [Team Onboarding](https://docs.google.com/document/d/1ukbpW4LSqkb_CCt8LWfpehP03qqfyYfvK3Fl21NaEq8/edit?usp=sharing)
- [ ] [Architecture Decision Records](https://github.com/cisagov/dotgov/tree/main/docs/architecture/decisions)
- [ ] [Contributing Policy](https://github.com/cisagov/dotgov/tree/main/CONTRIBUTING.md)


## Setting up commit signing with GPG

Follow the instructions [here](https://docs.github.com/en/authentication/managing-commit-signature-verification/generating-a-new-gpg-key) to generate a new GPG key (default configurations are okay) and add it to your GPG keys on Github.

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

## Setting up commit signing with SSH

Follow the instructions [here](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent#generating-a-new-ssh-key) to generate a new SSH key and [add it to your SSH keys on Github](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account). Note that you need to add the key as a signing key.

Configure your key locally:

```bash
git config --global gpg.format ssh
git config --global commit.gpgsign true
git config --global user.signingkey <YOUR KEY>
```

Where <YOUR KEY> is the path to the private key you generated when running `ssh-keygen`. Usually this is located in ~\.ssh\.

Now test commit signing is working by checking out a branch (`yourname/test-commit-signing`) and making some small change to a file. Commit the change (it should prompt you for your key passphrase) and push it to Github. Look on Github at your branch and ensure the commit is `verified`.

### MacOS
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
and then

```bash
source ~/.bashrc
```
or
```bash
source ~/.zshrc
```

### Windows
If GPG doesn't work out of the box with git for you:
- You can [download the GPG binary directly](https://gnupg.org/download/). 
- It may be helpful to use [gpg4win](https://www.gpg4win.org/get-gpg4win.html). 

From there, you should be able to access gpg through the terminal. 

Additionally, consider a gpg key manager like Kleopatra if you run into issues with environment variables or with the gpg service not running on startup. 

## Setting up developer sandbox

We have three types of environments: stable, staging, and sandbox. Stable (production)and staging (pre-prod) get deployed via tagged release, and developer sandboxes are given to get.gov developers to mess around in a production-like environment without disrupting stable or staging. Each sandbox is namespaced and will automatically be deployed too when the appropriate branch syntax is used for that space in an open pull request. There are several things you need to setup to make the sandbox work for a developer. 

All automation for setting up a developer sandbox is documented in the scripts for [creating a developer sandbox](../../ops/scripts/create_dev_sandbox.sh) and [removing a developer sandbox](../../ops/scripts/destroy_dev_sandbox.sh). A Cloud.gov organization administrator will have to perform the script in order to create the sandbox. 
