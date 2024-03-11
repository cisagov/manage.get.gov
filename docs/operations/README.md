# Operations

Some basic information and setup steps are included in this README.

Instructions for specific actions can be found in our [runbooks](./runbooks/).

## Continuous Delivery

We use a [cloud.gov service account](https://cloud.gov/docs/services/cloud-gov-service-account/) to deploy from this repository to cloud.gov with a SpaceDeveloper user.

## Authenticating to Cloud.gov via the command line

You'll need the [Cloud Foundry CLI](https://docs.cloud.gov/getting-started/setup/).

We use the V7 Cloud Foundry CLI.

```shell
cf login -a api.fr.cloud.gov --sso
```

After authenticating, make sure you are targeting the correct org and space!

```bash
cf spaces
cf target -o <ORG> -s <SPACE>
```

## Database

In sandbox, created with `cf create-service aws-rds micro-psql getgov-ENV-database`.

Binding the database in `manifest-<ENVIRONMENT>.json` automatically inserts the connection string into the environment as `DATABASE_URL`.

[Cloud.gov RDS documentation](https://cloud.gov/docs/services/relational-database/).

# Deploy

We have four types of environments: developer "sandboxes", `development`, `staging` and `stable`. Developers can deploy locally to their sandbox whenever they want. However, only our CD service can deploy to `development`, `staging` and `stable`.

For staging and stable our CD service completes this deploy when we make tagged releases from specifc branch. For `staging`, this is done to ensure there is a non-production level test environment that can be used for user testing or for testing code before it is pushed to `stable`. `Staging` can be especially helpful when testing database changes or migrations that could have adververse affects in `stable`. When deploying to staging, the branch used is often just `main`. On the other hand, `stable` is used to ensure that we have a "golden" environment to point to. We can refer to `stable` as our production environment and `staging` as our pre-production (pre-prod) environment. As such, code on main should always be tagged for `staging` before it is tagged for `stable`. Thus the branch used in `stable` releases is usually the tagged branch used for the last staging commit.

The `development` environment, is one that auto deploys on any push to main via our CD service. This is to ensure we have an environment that is identical to what we have on the `main` branch. This should not be confused with the "sandboxes" given to developers and designers for ticket development.

When deploying to your personal sandbox, you should make sure all of the USWDS assets are compiled and collected before deploying to your sandbox. To deploy locally to `sandbox`:

For ease of use, you can run the `deploy.sh <sandbox name>` script in the `/src` directory to build the assets and deploy to your sandbox. Similarly, you could run `build.sh <sandbox name>` script to just compile and collect the assets without deploying.

Your sandbox space should've been setup as part of the onboarding process. If this was not the case, please have an admin follow the instructions below.

## Creating a sandbox or new environment

When possible all developers and designers should have their own sandboxes as this provides them a space to test out changes in an isolated environment. All sandboxes are still accessible on the web, just like `staging`, `stable`, and `development`.

1. Make sure you have admin access to the cloud.gov organization, have admin access on github, and make sure you are targeting your own workspace in cloudfoundry
2. Make sure you are on `main` and your local code is up to date with the repo
3. Open the terminal to the root project directory 
4. run [creating a developer sandbox shell script](../../ops/scripts/create_dev_sandbox.sh) by typing the path to the script followed by the name of the sandbox you wish to create. Use initials for the sandbox name. If John Doe is the name of a developer you wish to make a sandbox for you would then do:

```
./ops/scripts/create_dev_sandbox.sh jd
```

5. Follow the prompts that appear in the terminal, if on `main`, make sure to click yes to switching to a new branch. Clicking anything besides `Y` or `y` will count as a no.
6. When the database is being set up it can take 5 mins or longer, don't close the window.
7. The last prompt asks if you want to make a PR, this will generate a PR for you but you may need to double check against similiar PRs to make sure everything was changed correctly. To do this go to github Pull Requests and search for closed PRs with the word infrastructure.

## Once the sandbox or new environment is made

Once this is made, the new owner of the sandbox has a few steps they should follow. This is already in [onboarding documents](https://docs.google.com/document/d/1ukbpW4LSqkb_CCt8LWfpehP03qqfyYfvK3Fl21NaEq8/edit#heading=h.6dw0iz1u56ox), but is worth re-iterating here:

1. Run fixtures if desired. Refer to the [onboarding guide](https://docs.google.com/document/d/1ukbpW4LSqkb_CCt8LWfpehP03qqfyYfvK3Fl21NaEq8/edit#heading=h.6dw0iz1u56ox) for how to do this and helpful hints
2. add environment variables for registrar-registry communication (EPP), see [the application secrets readme](./runbooks/rotate_application_secrets.md)


## Creating a new environment
If we ever need a new environment to replace `development`, `staging` or `stable` we need to follow similiar steps but not identical ones to the instructions for making a sandbox.

1. Just like making a sandbox make sure you have admin access to the cloud.gov organization, have admin access on github, and make sure you are targeting your own workspace in cloudfoundry.  Make sure you are on `main` and your local code is up to date with the repo
2. Open the terminal to the root project directory.
3. Instead of running [the script for creating a sandbox](../../ops/scripts/create_dev_sandbox.sh), you will manually copy over which commands you want directly into the terminal. Don't run the prompts in terminal, as you will be figuring out what you need to do based on your needs. All the prompts, denoted with `echo`, tell you what the following commands are doing. When uncertain look at the cloudfoundry documentation for any of the `cf` commands.
4. In most cases, the setup will be almost identical to making a sandbox. The main difference will be deployment and determining if you want workflows like reset, deploy, and migrate to work for it. You will manually update these yaml files if you want the workflows included.
5. Often it is the manifest file that needs to change as well, either with different environment variables, number of instances, or so on. Copy whichever manifest is closest to what you wish to do and tailor it to your specific needs. See cloudfoundry's and docker's documentation if you need assistance.

## Stable and Staging Release Rules

Releases will be made for staging and stable twice a week, ideally Tuesday and Thursday, but can be adjusted if needed. Code on `main` will be released to `staging`, and then on the following Tuesday/Thursday this `staging` release will become the new `stable` release. This means every release day, a release will be made to `stable` containing the last `staging` code. On this same day a new `staging` release will be made that contains the most up-to-date code on main. Thus, `staging` can be a few days behind the main branch, and `stable` will be a few days behind the code on `staging`.

If a bug fix or feature needs to be made to stable out of the normal cycle, this can only be done at the product owner's request.

## Making bug fixes on stable during production

In the case where a bug fix or feature needs to be added outside of the normal cycle, the code-fix branch and release will be handled differently than normal:

1. Code will need to be branched NOT off of main, but off of the same commit as the most recent stable commit. This should be the one tagged with the most recent vX.XX.XX value.
2. After making the bug fix, the approved PR branch will not be merged yet, instead it will be tagged with a new release tag, incrementing the patch value from the last commit number.
3. If main and stable are on the the same commit then merge this branch into staging using the staging release tag (staging-<the hotfix release number>). 
4. If staging is already ahead stable, you may need to create another branch that is based off of the current staging commit, merge in your code change and then tag that branch with the staging release.
5. Wait to merge your original branch until both deploys finish. Once they succeed then merge to main per the usual process.

## Serving static assets
We are using [WhiteNoise](http://whitenoise.evans.io/en/stable/index.html) plugin to serve our static assets on cloud.gov. This plugin is added to the `MIDDLEWARE` list in our apps `settings.py`.

Note that it’s a good idea to run `collectstatic` locally or in the docker container before pushing files up to your sandbox. This is because `collectstatic` relies on timestamps when deciding to whether to overwrite the existing assets in `/public`. Due the way files are uploaded, the compiled css in the `/assets/css` folder on your sandbox will have a slightly earlier timestamp than the files in `/public/css`, and consequently running `collectstatic` on your sandbox will not update `public/css` as you may expect. For convenience, both the `deploy.sh` and `build.sh` scripts will take care of that. 

# Debugging

Debugging errors observed in applications running on Cloud.gov requires being
able to see the log information from the environment that the application is
running in. There are (at least) three different ways to see that information:
Cloud.gov dashboard, CloudFoundry CLI application, and Cloud.gov Kibana logging
queries. There is also SSH access into Cloud.gov containers and Github Actions
that can be used for specific tasks.

## Cloud.gov dashboard

At <https://dashboard.fr.cloud.gov/applications> there is a list for all of the
applications that a Cloud.gov user has access to. Clicking on a domain request
goes to a screen for that individual application, e.g.
<https://dashboard.fr.cloud.gov/applications/2oBn9LBurIXUNpfmtZCQTCHnxUM/53b88024-1492-46aa-8fb6-1429bdb35f95/summary>.
On that page is a left-hand link for "Log Stream" e.g.
<https://dashboard.fr.cloud.gov/applications/2oBn9LBurIXUNpfmtZCQTCHnxUM/53b88024-1492-46aa-8fb6-1429bdb35f95/log-stream>.
That log stream shows a stream of Cloud.gov log messages. Cloud.gov has
different layers that log requests. One is `RTR` which is the router within
Cloud.gov. Messages from our Django app are prefixed with `APP/PROC/WEB`. While
it is possible to search inside the browser for particular log messages, this
is not a sophisticated interface for querying logs.

## CloudFoundry CLI

When logged in with the CloudFoundry CLI (see
[above](#authenticating-to-cloudgov-via-the-command-line)) Cloudfoundry
application logs can be viewed with the `cf logs <application>` where
`<application>` is the name of the application in the currently targeted space.
By default `cf logs` starts a streaming view of log messages from the
application. It appears to show the same information as the dashboard web
application, but in the terminal. There is a `--recent` option that will dump
things that happened prior to the current time rather than starting a stream of
the present log messages, but that is also not a full log archive and search
system.

CloudFoundry also offers a `run-task` command that can be used to run a single
command in the running Cloud.gov container. For example, to run our Django
admin command that loads test fixture data:

```
cf run-task getgov-{environment} --command "./manage.py load" --name fixtures--users
cf run-task getgov-{environment} --command "./manage.py load" --name fixtures--applications
```

However, this task runs asynchronously in the background without any command
output, so it can sometimes be hard to know if the command has completed and if
so, if it was successful.

## Cloud.gov Kibana

Cloud.gov provides an instance of the log query program Kibana at
<https://logs.fr.cloud.gov>. Kibana is powerful, but also complicated software
that can take time to learn how to use most effectively. A few hints:

  - Set the timeframe of the display appropriately, the default is the last
    15 minutes which may not show any results in some environments.

  - Kibana queries and filters can be used to narrow in on particular
    environments. Try the query `@source.type:APP` to focus on messages from the
    Django application or `@cf.app:"getgov-{environment}"` to see results from a single
    environment.

Currently, our application emits Python's default log format which is textual
and not record-based. In particular, tracebacks are on multiple lines and show
up in Kibana as multiple records that are not necessarily connected. As the
application gets closer to production, we may want to switch to a JSON log format
where errors will be captured by Kibana as a single message, however with a
slightly more difficult developer experience when reading logs by eyeball.


## SSH access

The CloudFoundry CLI provides SSH access to the running container of an
application. Use `cf ssh <application>` to SSH into the container. To make sure
that your shell is seeing the same configuration as the running application, be
sure to run `/tmp/lifecycle/shell` very first.

Inside the container, the python code should be in `/app` and you can check
there to see if the expected version of code is deployed in a particular file.
There is no hot-reloading inside the container, so it isn't possible to make
code changes there and see the results reflected in the running application.
(Templates may be read directly from disk every page load so it is possible
that you could change a page template and see the result in the application.)

Inside the container, it can be useful to run various Django admin commands
using `./manage.py`. For example, `./manage.py shell` can be used to give a
python interpreter where code can be run to modify objects in the database, say
to make a user an administrator.

## Github Actions

In order to allow some ops activities by people without CloudFoundry on a
laptop, we have some ops-related actions under
<https://github.com/cisagov/getgov/actions>.

### Migrate data

This Github action runs Django's `manage.py migrate` command on the specified
environment. **This is the first thing to try when fixing 500 errors from an
application environment**. The migrations should be idempotent, so running the
same migrations more than once should never cause an additional problem.

### Reset database

Very occasionally, there are migrations that don't succeed when run against a
database with data already in it. This action drops the database and re-creates
it with the latest model schema. Once launched, this should never be used on
the `stable` environment, but during development, it may be useful on the
various sandbox environments. After launch, some schema changes may take the
involvement of a skilled DBA to fix problems like this.

# Bug triage

Bugs on production software need to be documented quickly and triaged to determine if fixes need to be made outside of the normal release cadence. Triage levels will be Critical, High, Medium, and Low to indicate the level of priority for fix, not neccessarily the level of severity. See below for more details

**Critical**- should only be determined by the product owner and means the fix for this critical bug needs to have a quick fix for it created ASAP. This is the only case where a bug fix can be added outside of the normal release cycle and directly onto the stable release.
**High**- Can be determined by product owner or other team member, and indicates this bug is critical enough to warrant being added into the current sprint.
**Medium**- Should be added to a sprint coming up but is not blocking users, or enough users to warrant rushing it into a sprint
**Low**- A minor bug, that could even wait until after the next big launch date to be implemented.

## Steps for Triaging

1. When a bug is found, whether by a developer/designer or from feedback from an end user, a ticket should be made immediately. The actual maker of the ticket can be a member of the product team as needed.
2. This bug ticket immediately gets a priority added Critical/High/Medium/Low, with Critical requiring the product owner's consent.
3. Anything marked as `critical` should be refined immediately and engineering should be notified in our Slack dev channel that a Critical ticket has been created (if not already notified)
4. All items not marked as `critical` by the product owner can wait until refinement to be refined and may have their prioirty level changed during that meeting.

## Steps for dealing with Critical Bugs

1. Once the critical bug ticket is refined and the bug is clear, an engineer should be assigned to work on it. (No ticket, no work)
2. At the same point, two other engineers should be assigned to review the PR once it's made. One of the reviewing engineers can be subsititued for a designer if this is a design/content/other user facing bug fix.
3. In the case where the engineering lead is is unresponsive or unavailable to assign the ticket immediately, the product team will make sure an engineer volunteers or is assigned to the ticket/PR review ASAP.
4. Once done, the developer must make a PR and should tag the assigned PR reviewers in our Slack dev channel stating that the PR is now waiting on their review. These reviewers should drop other tasks in order to review this promptly.
5. See the the section above on [Making bug fixes on stable](#making-bug-fixes-on-stable-during-production) for how to push changes to stable once the PR is approved

# Investigating and monitoring the health of the Registrar

Sometimes, we may want individuals to routinely monitor the Registrar's health, such as after big feature launches. The cadence of such monitoring and what we look for is subject to change and is instead documented in [Checklist for production verification document](https://docs.google.com/document/d/15b_qwEZMiL76BHeRHnznV1HxDQcxNRt--vPSEfixBOI). All project team members should feel free to suggest edits to this document and should refer to it if production-level monitoring is underway.