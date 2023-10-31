# Registrar Data Migration

The original system has an existing registrar/registry that we will import.
The company of that system will provide us with an export of the data.
The goal of our data migration is to take the provided data and use
it to create as much as possible a _matching_ state
in our registrar.

There is no way to make our registrar _identical_ to the original system
because we have a different data model and workflow model. Instead, we should
focus our migration efforts on creating a state in our new registrar that will
primarily allow users of the system to perform the tasks that they want to do.

## Users

One of the major differences with the existing registrar/registry is that our
system uses Login.gov for authentication. Any person with an identity-verified
Login.gov account can make an account on the new registrar, and the first time
that person logs in through Login.gov, we make a corresponding account in our
user table. Because we cannot know the Universal Unique ID (UUID) for a
person's Login.gov account, we cannot pre-create user accounts for individuals
in our new registrar based on the original data.

## Domains

Our registrar keeps track of domains. The authoritative source for domain
information is the registry, but the registrar needs a copy of that
information to make connections between registry users and the domains that
they manage. The registrar stores very few fields about a domain except for
its name, so it could be straightforward to import the exported list of domains
from `escrow_domains.daily.dotgov.GOV.txt`. It doesn't appear that
that table stores a flag for active or inactive.

An example Django management command that can load the delimited text file
from the daily escrow is in
`src/registrar/management/commands/load_domains_data.py`. It uses Django's
object-relational modeler (ORM) to create Django objects for the domains and
then write them to the database in a single bulk operation. To run the command
locally for testing, using Docker Compose:

```shell
docker compose run -T app ./manage.py load_domains_data < /tmp/escrow_domains.daily.dotgov.GOV.txt
```

## User access to domains

The data export contains a `escrow_domain_contacts.daily.dotgov.txt` file
that links each domain to three different types of contacts: `billing`,
`tech`, and `admin`. The ID of the contact in this linking table corresponds
to the ID of a contact in the `escrow_contacts.daily.dotgov.txt` file. In the
contacts file is an email address for each contact.

The new registrar associates user accounts (authenticated with Login.gov) with
domains using a `UserDomainRole` linking table. New users can be granted roles
on domains by creating a `DomainInvitation` that links an email address with a
domain. When a new user finishes authenticating with Login.gov and their email
address matches an invitation, then they are given the appropriate role on the
invitation's domain.

For the purposes of migration, we can prime the invitation system by creating
an invitation in the system for each email address listed in the
`domain_contacts` file. This means that if a person is currently a user in the
original system, and they use the same email address with Login.gov, then they
will end up with access to the same domains in the new registrar that they
were associated with in the original system.

A management command that does this needs to process two data files, one for
the contact information and one for the domain/contact association, so we
can't use stdin the way that we did before. Instead, we can use the fact that
Docker Compose mounts the `src/` directory inside of the container at `/app`.
Then, data files that are inside of the `src/` directory can be accessed
inside the Docker container.

An example script using this technique is in
`src/registrar/management/commands/load_domain_invitations.py`.

```shell
docker compose run app ./manage.py load_domain_invitations /app/escrow_domain_contacts.daily.dotgov.GOV.txt /app/escrow_contacts.daily.dotgov.GOV.txt
```

## Transition Domains
We are provided with information about Transition Domains in 3 files:
FILE 1: **escrow_domain_contacts.daily.gov.GOV.txt** -> has the map of domain names to contact ID. Domains in this file will usually have 3 contacts each
FILE 2: **escrow_contacts.daily.gov.GOV.txt** -> has the mapping of contact id to contact email address (which is what we care about for sending domain invitations)
FILE 3: **escrow_domain_statuses.daily.gov.GOV.txt** -> has the map of domains and their statuses

We need to run a few scripts to parse these files into our domain tables.
We can do this both locally and in a sandbox.

### SANDBOX MIGRATION SETUP
### Load migration data onto a production or sandbox environment
**WARNING:** All files uploaded in this manner are temporary, i.e. they will be deleted when the app is restaged.
Do not use this method to store data you want to keep around permanently.

#### STEP 1: Use scp to transfer data
CloudFoundry supports scp as means of transferring data locally to our environment. If you are dealing with a batch of files, try sending across a tar.gz and unpacking that.

**Login to Cloud.gov**

```bash
cf login -a api.fr.cloud.gov  --sso
```

**Target your workspace**

```bash
cf target -o cisa-dotgov -s {SANDBOX_NAME}
```
*SANDBOX_NAME* - Name of your sandbox, ex: za or ab

**Run the scp command**

Use the following command to transfer the desired file:
```shell
scp -P 2222 -o User=cf:$(cf curl /v3/apps/$(cf app {FULL_NAME_OF_YOUR_SANDBOX_HERE} --guid)/processes | jq -r '.resources[]
| select(.type=="web") | .guid')/0 {LOCAL_PATH_TO_FILE} ssh.fr.cloud.gov:tmp/{DESIRED_NAME_OF_FILE}
```
The items in curly braces are the values that you will manually replace.
These are as follows:
* FULL_NAME_OF_YOUR_SANDBOX_HERE - Name of your sandbox, ex: getgov-za
* LOCAL_PATH_TO_FILE - Path to the file you want to copy, ex: src/tmp/escrow_contacts.daily.gov.GOV.txt
* DESIRED_NAME_OF_FILE - Use this to specify the filename and type, ex: test.txt or escrow_contacts.daily.gov.GOV.txt

NOTE: If you'd wish to change what directory these files are uploaded to, you can change `ssh.fr.cloud.gov:tmp/` to `ssh.fr.cloud.gov:{DIRECTORY_YOU_WANT}/`, but be aware that this makes data migration more tricky than it has to be.

**Get a temp auth code**

The scp command requires a temporary authentication code. Open a new terminal instance (while keeping the current one open),
and enter the following command:
```shell
cf ssh-code
```
Copy this code into the password prompt from earlier.

NOTE: You can use different utilities to copy this onto the clipboard for you. If you are on Windows, try the command `cf ssh-code | clip`. On Mac, this will be `cf ssh-code | pbcopy`

#### STEP 2: Transfer uploaded files to the getgov directory
Due to the nature of how Cloud.gov operates, the getgov directory is dynamically generated whenever the app is built under the tmp/ folder. We can directly upload files to the tmp/ folder but cannot target the generated getgov folder directly, as we need to spin up a shell to access this. From here, we can move those uploaded files into the getgov directory using the `cat` command. Note that you will have to repeat this for each file you want to move, so it is better to use a tar.gz for multiple, and unpack it inside of the `datamigration` folder.

**SSH into your sandbox**

```shell
cf ssh {FULL_NAME_OF_YOUR_SANDBOX_HERE}
```

**Open a shell**

```shell
/tmp/lifecycle/shell
```

From this directory, run the following command:
```shell
./manage.py cat_files_into_getgov --file_extension txt
```

NOTE: This will look for all files in /tmp with the .txt extension, but this can
be changed if you are dealing with different extensions. For instance, a .tar.gz could be expressed
as `--file_extension tar.gz`.

If you are using a tar.gz file, you will need to perform one additional step to extract it.
Run the following command from the same directory:
```shell
tar -xvf migrationdata/{FILE_NAME}.tar.gz -C migrationdata/ --strip-components=1
```

*FILE_NAME* - Name of the desired file, ex: exportdata



##### Manual method
If the `cat_files_into_getgov.py` script isn't working, follow these steps instead.

**Move the desired file into the correct directory**

```shell
cat ../tmp/{filename} > migrationdata/{filename}
```


#### You are now ready to run migration scripts (see "Running the Migration Scripts")
```

```
### LOCAL MIGRATION SETUP (TESTING PURPOSES ONLY)
### Load migration data onto our local environments

***IMPORTANT: only use test data, to avoid publicizing PII in our public repo.***

In order to run the scripts locally, we need to add the files to a folder under `src/`.
This will allow Docker to mount the files to a container (under `/app`) for our use.  

 - Create a folder called `tmp` underneath `src/`
 - Add the above files to this folder
 - Open a terminal and navigate to `src/`

#### You are now ready to run migration scripts (see "Running the Migration Scripts")

### RUNNING THE MIGRATION SCRIPTS

**NOTE: Whil we recommend executing the following scripts individually (Steps 1-3), migrations can also be done 'all at once' using the "Run Migration Feature" in step 4.  Use with discretion.**

#### 1 - Load Transition Domains
Run the following command  (This will parse the three files in your `tmp` folder and load the information into the TransitionDomain table);
```shell
docker compose run -T app ./manage.py load_transition_domain /app/tmp/escrow_domain_contacts.daily.gov.GOV.txt /app/tmp/escrow_contacts.daily.gov.GOV.txt /app/tmp/escrow_domain_statuses.daily.gov.GOV.txt --debug
```

**For Sandbox**:
Change "/app/tmp" to point to the sandbox directory

**OPTIONAL COMMAND LINE ARGUMENTS**: 
`--debug`
This will print out additional, detailed logs.

`--limitParse 100` 
Directs the script to load only the first 100 entries into the table.  You can adjust this number as needed for testing purposes.  

`--resetTable`
This will delete all the data in transtion_domain.  It is helpful if you want to see the entries reload from scratch or for clearing test data.


### STEP 2: Transfer Transition Domain data into main Domain tables

Now that we've loaded all the data into TransitionDomain, we need to update the main Domain and DomainInvitation tables with this information.  

In the same terminal as used in STEP 1, run the command below; 
(This will parse the data in TransitionDomain and either create a corresponding Domain object, OR, if a corresponding Domain already exists, it will update that Domain with the incoming status. It will also create DomainInvitation objects for each user associated with the domain):
```shell
docker compose run -T app ./manage.py transfer_transition_domains_to_domains --debug
```

**OPTIONAL COMMAND LINE ARGUMENTS**: 
`--debug`
This will print out additional, detailed logs.

`--limitParse 100` 
Directs the script to load only the first 100 entries into the table.  You can adjust this number as needed for testing purposes.  

### STEP 3: Send Domain invitations
### Run the send invitations script

To send invitations for every transition domain in the transition domain table, execute the following command:
`docker compose run -T app send_domain_invitations -s`

### STEP 4: Test the results
### Run the migration analyzer

This script's main function is to scan the transition domain and domain tables for any anomalies.  It produces a simple report of missing or duplicate data.  NOTE: some missing data might be expected depending on the nature of our migrations so use best judgement when evaluating the results.

**ANALYZE ONLY**
To analyze our database without running migrations, execute the script without any optional arguments:
`docker compose run -T app ./manage.py master_domain_migrations --debug`

**RUN MIGRATIONS FEATURE**
To run the migrations again (all above migration steps) before analyzing, execute the following command (read the documentation on the terminal arguments below.  Everything used by the migration scripts can also be passed into this script and will have the same effects).  NOTE: --debug and --prompt allow you to step through the migration process and exit it after each step if you need to.  It is recommended that you use these arguments when using the --runMigrations feature:
`docker compose run -T app ./manage.py master_domain_migrations --runMigrations --debug --prompt`

#### OPTIONAL ARGUMENTS
`--runMigrations`
A boolean (default to true), which triggers running
all scripts (in sequence) for transition domain migrations

`--migrationDirectory`
**default="migrationData"** (<--This is the sandbox directory)
The location of the files used for load_transition_domain migration script
EXAMPLE USAGE:
--migrationDirectory /app/tmp

`--migrationFilenames`
**default=escrow_domain_contacts.daily.gov.GOV.txt,escrow_contacts.daily.gov.GOV.txt,escrow_domain_statuses.daily.gov.GOV.txt** (<--These are the usual names for the files.  The script will throw a warning if it cannot find these exact files, in which case you will need to supply the correct filenames)
The files used for load_transition_domain migration script.
Must appear IN ORDER and comma-delimited: 
EXAMPLE USAGE:
--migrationFilenames domain_contacts_filename.txt,contacts_filename.txt,domain_statuses_filename.txt
where...
- domain_contacts_filename is the Data file with domain contact information
- contacts_filename is the Data file with contact information
- domain_statuses_filename is the Data file with domain status information

`--sep`
Delimiter for the migration scripts to correctly parse the given text files.
(usually this can remain at default value of |)

`--debug`
A boolean (default to true), which activates additional print statements

`--prompt`
A boolean (default to true), which activates terminal prompts
that allows the user to step through each portion of this
script.

`--limitParse`
Used by the migration scripts (load_transition_domain) to set the limit for the
number of data entries to insert.  Set to 0 (or just don't use this
argument) to parse every entry. This was provided primarily for testing
purposes

`--resetTable`
Used by the migration scripts to trigger a prompt for deleting all table entries.  
Useful for testing purposes, but USE WITH CAUTION
```