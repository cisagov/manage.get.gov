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

## Transition Domains (Part 1) - Setup Files for Import

#### STEP 1: obtain data files
We are provided with information about Transition Domains in the following files:

- FILE 1: **escrow_domain_contacts.daily.gov.GOV.txt** -> has the map of domain names to contact ID. Domains in this file will usually have 3 contacts each
- FILE 2: **escrow_contacts.daily.gov.GOV.txt** -> has the mapping of contact id to contact email address (which is what we care about for sending domain invitations)
- FILE 3: **escrow_domain_statuses.daily.gov.GOV.txt** -> has the map of domains and their statuses
- FILE 4: **escrow_domains.daily.dotgov.GOV.txt** -> has a map of domainname, expiration and creation dates
- FILE 5: **domainadditionaldatalink.adhoc.dotgov.txt** -> has the map of domains to other data like authority, organization, & domain type
- FILE 6: **domaintypes.adhoc.dotgov.txt** -> has data on federal type and organization type
- FILE 7: **organization.adhoc.dotgov.txt** -> has organization name data
- FILE 8: **authority.adhoc.dotgov.txt** -> has authority data which maps to an agency
- FILE 9: **agency.adhoc.dotgov.txt** -> has federal agency data
- FILE 10: **migrationFilepaths.json** -> A JSON which points towards all given filenames. Specified below.

#### STEP 2: obtain JSON file (for file locations)
Add a JSON file called "migrationFilepaths.json" with the following contents (update filenames and directory as needed):
```
{
    "directory": "migrationdata",
    "contacts_filename": "escrow_contacts.daily.dotgov.GOV.txt",
    "domain_contacts_filename": "escrow_domain_contacts.daily.dotgov.GOV.txt",
    "domain_statuses_filename": "escrow_domain_statuses.daily.dotgov.GOV.txt",
    "domain_escrow_filename": "escrow_domains.daily.dotgov.GOV.txt",
    "domain_additional_filename": "domainadditionaldatalink.adhoc.dotgov.txt",
    "domain_adhoc_filename": "domaintypes.adhoc.dotgov.txt",
    "organization_adhoc_filename": "organization.adhoc.dotgov.txt"
    "authority_adhoc_filename": "authority.adhoc.dotgov.txt",
    "agency_adhoc_filename": "agency.adhoc.dotgov.txt",
}
```

This JSON file can exist anywhere, but to keep things simple, add it to the same folder as used in step 1.  `src/migrationdata`. 
Directory specifies the directory that the given `filenames` exist in. For instance, a `contacts_filename` of `test.txt` with a `directory` of `migrationdata` would need to exist under `migrationdata/test.txt`.

Later on, we will bundle this file along with the others into its own folder. Keep it within the `migrationdata/` directory if you are passing data to your sandbox, for simplicity.

We need to run a few scripts to parse these files into our domain tables.
We can do this both locally and in a sandbox.

#### STEP 3: Bundle all relevant data files into an archive
Move all the files specified in Step 1 into a shared folder, and create a tar.gz.

Create a folder on your desktop called `datafiles` and move all of the obtained files into that. Add these files to a tar.gz archive using any method. See (here)[https://stackoverflow.com/questions/53283240/how-to-create-tar-file-with-7zip].

After this is created, move this archive into `src/migrationdata`.


### SECTION 1 - SANDBOX MIGRATION SETUP
Load migration data onto a production or sandbox environment

**WARNING:** All files uploaded in this manner are temporary, i.e. they will be deleted when the app is restaged.
Do not use these environments to store data you want to keep around permanently. We don't want sensitive data to be accidentally present in our application environments.

#### STEP 1: Using cat to transfer data to sandboxes

```bash
cat {LOCAL_PATH_TO_FILE} | cf ssh {APP_NAME_IN_ENVIRONMENT} -c "cat > /home/vcap/tmp/{DESIRED_NAME_OF_FILE}"
```

* APP_NAME_IN_ENVIRONMENT - Name of the app running in your environment, e.g. getgov-za or getgov-stable
* LOCAL_PATH_TO_FILE - Path to the file you want to copy, ex: src/tmp/escrow_contacts.daily.gov.GOV.txt
* DESIRED_NAME_OF_FILE - Use this to specify the filename and type, ex: test.txt or escrow_contacts.daily.gov.GOV.txt

**TROUBLESHOOTING:** Depending on your operating system (Windows for instance), this command may upload corrupt data. If you encounter the error `gzip: prfiles.tar.gz: not in gzip format` when trying to unzip a .tar.gz file, use the scp command instead.

#### STEP 1 (Alternative): Using scp to transfer data to sandboxes
**IMPORTANT:** Only follow these steps if cat does not work as expected. If it does, skip to step 2.

CloudFoundry supports scp as means of transferring data locally to our environment. If you are dealing with a batch of files, try sending across a tar.gz and unpacking that.

##### Login to Cloud.gov

```bash
cf login -a api.fr.cloud.gov  --sso
```

##### Target your workspace

```bash
cf target -o cisa-dotgov -s {ENVIRONMENT_NAME}
```
*ENVIRONMENT_NAME* - Name of your sandbox, ex: za or ab

##### Run the scp command

Use the following command to transfer the desired file:
```shell
scp -P 2222 -o User=cf:$(cf curl /v3/apps/$(cf app {APP_NAME_IN_ENVIRONMENT} --guid)/processes | jq -r '.resources[]
| select(.type=="web") | .guid')/0 {LOCAL_PATH_TO_FILE} ssh.fr.cloud.gov:tmp/{DESIRED_NAME_OF_FILE}
```
The items in curly braces are the values that you will manually replace.
These are as follows:
* APP_NAME_IN_ENVIRONMENT - Name of the app running in your environment, e.g. getgov-za or getgov-stable
* LOCAL_PATH_TO_FILE - Path to the file you want to copy, ex: src/tmp/escrow_contacts.daily.gov.GOV.txt
* DESIRED_NAME_OF_FILE - Use this to specify the filename and type, ex: test.txt or escrow_contacts.daily.gov.GOV.txt

##### Get a temp auth code

The scp command requires a temporary authentication code. Open a new terminal instance (while keeping the current one open),
and enter the following command:
```shell
cf ssh-code
```
Copy this code into the password prompt from earlier.

NOTE: You can use different utilities to copy this onto the clipboard for you. If you are on Windows, try the command `cf ssh-code | clip`. On Mac, this will be `cf ssh-code | pbcopy`

#### STEP 2: Transfer uploaded files to the getgov directory
Due to the nature of how Cloud.gov operates, the getgov directory is dynamically generated whenever the app is built under the tmp/ folder. We can directly upload files to the tmp/ folder but cannot target the generated getgov folder directly, as we need to spin up a shell to access this. From here, we can move those uploaded files into the getgov directory using the `cat` command. Note that you will have to repeat this for each file you want to move, so it is better to use a tar.gz for multiple, and unpack it inside of the `datamigration` folder.

##### SSH into your sandbox

```shell
cf ssh {APP_NAME_IN_ENVIRONMENT}
```

##### Open a shell

```shell
/tmp/lifecycle/shell
```

##### From this directory, run the following command:
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


#### Manual method
If the `cat_files_into_getgov.py` script isn't working, follow these steps instead.

##### Move the desired file into the correct directory

```shell
cat ../tmp/{filename} > migrationdata/{filename}
```


*You are now ready to run migration scripts (see [Running the Migration Scripts](running-the-migration-scripts))*

### SECTION 2 - LOCAL MIGRATION SETUP (TESTING PURPOSES ONLY)

***IMPORTANT: only use test data, to avoid publicizing PII in our public repo.***

In order to run the scripts locally, we need to add the files to a folder under `src/`.
This will allow Docker to mount the files to a container (under `/app`) for our use.  

 - Add the same files from section 1 to a TEMPORARY `tmp/` folder under `src/` (do not check this folder into our repo)
 - Open a terminal and navigate to `src/`


*You are now ready to run migration scripts.*

## Transition Domains (Part 2) - Running the Migration Scripts
While keeping the same ssh instance open (if you are running on a sandbox), run through the following commands.If you cannot run `manage.py` commands, try running `/tmp/lifecycle/shell` in the ssh instance. 

### STEP 1: Load Transition Domains

Run the following command, making sure the file paths point to the right location. This will parse all given files and load the information into the TransitionDomain table. Make sure you have your migrationFilepaths.json file in the same directory.

```
##### LOCAL COMMAND
```shell
docker-compose exec app ./manage.py load_transition_domain migrationFilepaths.json --directory /app/tmp/ --debug --limitParse 10
```
##### SANDBOX COMMAND
```shell
./manage.py load_transition_domain migrationFilepaths.json --debug
```

##### COMMAND LINE ARGUMENTS:

`--debug`
This will print out additional, detailed logs.

`--limitParse 100` 
Directs the script to load only the first 100 entries into the table.  You can adjust this number as needed for testing purposes.  

`--resetTable`
This will delete all the data in transtion_domain.  It is helpful if you want to see the entries reload from scratch or for clearing test data.

###### (arguments that override filepaths and directories if needed)

`--directory`
Defines the directory where all data files and the JSON are stored.

`--domain_contacts_filename`
Defines the filename for domain contact information.

`--contacts_filename`
Defines the filename for contact information.

`--domain_statuses_filename`
Defines the filename for domain status information.
            
`--agency_adhoc_filename`
Defines the filename for agency adhocs.

`--domain_additional_filename`
Defines the filename for additional domain data.

`--domain_escrow_filename`
Defines the filename for creation/expiration domain data.

`--domain_adhoc_filename`
Defines the filename for domain type adhocs.

`--organization_adhoc_filename`
Defines the filename for domain type adhocs.

`--authority_adhoc_filename`
Defines the filename for domain type adhocs.

`--infer_filenames`
Determines if we should infer filenames or not. This setting is not available for use in environments with the flag `settings.DEBUG` set to false, as it is intended for local development only.

### STEP 2: Transfer Transition Domain data into main Domain tables

Now that we've loaded all the data into TransitionDomain, we need to update the main Domain and DomainInvitation tables with this information.  
In the same terminal as used in STEP 1, run the command below; 
(This will parse the data in TransitionDomain and either create a corresponding Domain object, OR, if a corresponding Domain already exists, it will update that Domain with the incoming status. It will also create DomainInvitation objects for each user associated with the domain):

##### LOCAL COMMAND
```shell
docker compose run -T app ./manage.py transfer_transition_domains_to_domains --debug
```
##### SANDBOX COMMAND
```shell
./manage.py transfer_transition_domains_to_domains --debug
```

##### COMMAND LINE ARGUMENTS:

`--debug`
This will print out additional, detailed logs.

`--limitParse 100` 
Directs the script to load only the first 100 entries into the table.  You can adjust this number as needed for testing purposes.  

### STEP 3: Send Domain invitations

To send invitation emails for every transition domain in the transition domain table, execute the following command:

##### LOCAL COMMAND
```shell
docker compose run -T app ./manage.py send_domain_invitations -s
```
##### SANDBOX COMMAND
```shell
./manage.py send_domain_invitations -s
```

### STEP 4: Test the results (Run the analyzer script)

This script's main function is to scan the transition domain and domain tables for any anomalies.  It produces a simple report of missing or duplicate data.  NOTE: some missing data might be expected depending on the nature of our migrations so use best judgement when evaluating the results.

#### OPTION 1 - ANALYZE ONLY

To analyze our database without running migrations, execute the script without any optional arguments:

##### LOCAL COMMAND
```shell
docker compose run -T app ./manage.py master_domain_migrations --debug
```
##### SANDBOX COMMAND
```shell
./manage.py master_domain_migrations --debug
```

#### OPTION 2 - RUN MIGRATIONS FEATURE

To run the migrations again (all above migration steps) before analyzing, execute the following command (read the documentation on the terminal arguments below.  Everything used by the migration scripts can also be passed into this script and will have the same effects).  NOTE: --debug provides detailed logging statements during the migration.  It is recommended that you use this argument when using the --runMigrations feature:

(NOTE: If you named your JSON file something other than "migrationFilepaths.json" (all the way back in the "file setup" section).  You will want to utilize the `--migrationJSON` argument in the following commands...)
##### LOCAL COMMAND
```shell
docker compose run -T app ./manage.py master_domain_migrations --migrationDirectory /app/tmp --runMigrations --debug
```
##### SANDBOX COMMAND
```shell
./manage.py master_domain_migrations --runMigrations --debug
```

##### COMMAND LINE ARGUMENTS

`--runMigrations`

Runs all scripts (in sequence) for transition domain migrations

`--migrationDirectory`

The location of both the JSON file and all files needed for migration.
(default is "migrationdata" (This is the sandbox directory))

Example Usage:
*--migrationDirectory /app/tmp*

`--migrationJSON` 

The filename of the JSON that holds all the filepath info needed for migrations.

Example Usage:
*--migrationJSON migrationFilepaths.json*

`--sep`

Delimiter for the migration scripts to correctly parse the given text files.
(usually this can remain at default value of |)

`--debug`

Activates additional print statements

`--disablePrompts`

Disables the terminal prompts that allows the user to step through each portion of this script.
*used to facilitate unit tests.  Not recommended for everyday use*

`--limitParse`

Used by the migration scripts (load_transition_domain) to set the limit for the
number of data entries to insert.  Set to 0 (or just don't use this
argument) to parse every entry. This was provided primarily for testing
purposes

`--resetTable`

Used by the migration scripts to trigger a prompt for deleting all table entries.  
Useful for testing purposes, but *use with caution*

## Import organization data
During MVP, our import scripts did not populate the following fields: `address_line, city, state_territory, and zipcode`. This was primarily due to time constraints. Because of this, we need to run a follow-on script to load this remaining data on each `DomainInformation` object.

This script is intended to run under the assumption that the [load_transition_domain](#step-1-load-transition-domains) and the [transfer_transition_domains_to_domains](#step-2-transfer-transition-domain-data-into-main-domain-tables) scripts have already been ran.

##### LOCAL COMMAND
to run this command locally, enter the following:
```shell
docker compose run -T app ./manage.py load_organization_data {filename_of_migration_json} --debug
```
* filename_of_migration_filepath_json - This is a [JSON containing a list of filenames](#step-2-obtain-json-file-for-file-locations). This same file was used in the preceeding steps, `load_transition_domain` and `transfer_transition_domains_to_domains`, however, this script only needs two fields:
```
{
    "domain_additional_filename": "example.domainadditionaldatalink.adhoc.dotgov.txt",
    "organization_adhoc_filename": "example.organization.adhoc.dotgov.txt"
}
```
If you already possess the old JSON, you do not need to modify it. This script can run even if you specify multiple filepaths. It will just skip over unused ones. 

**Example**
```shell
docker compose run -T app ./manage.py load_organization_data migrationFilepaths.json --debug
```

##### SANDBOX COMMAND
```shell
./manage.py load_organization_data {filename_of_migration_json} --debug
```
* **filename_of_migration_filepath_json** - This is a [JSON containing a list of filenames](#step-2-obtain-json-file-for-file-locations). This same file was used in the preceeding steps, `load_transition_domain` and `transfer_transition_domains_to_domains`, however, this script only needs two fields:
```
{
    "domain_additional_filename": "example.domainadditionaldatalink.adhoc.dotgov.txt",
    "organization_adhoc_filename": "example.organization.adhoc.dotgov.txt"
}
```
If you already possess the old JSON, you do not need to modify it. This script can run even if you specify multiple filepaths. It will just skip over unused ones. 

**Example**
```shell
./manage.py load_organization_data migrationFilepaths.json --debug
```

##### Optional parameters
The `load_organization_data` script has five optional parameters. These are as follows:
|   | Parameter                        | Description                                                                 |
|:-:|:---------------------------------|:----------------------------------------------------------------------------|
| 1 | **sep**                          | Determines the file separator. Defaults to "\|"                             |
| 2 | **debug**                        | Increases logging detail. Defaults to False                                 |
| 3 | **directory**                    | Specifies the containing directory of the data. Defaults to "migrationdata" |
| 4 | **domain_additional_filename**   | Specifies the filename of domain_additional. Used as an override for the JSON. Has no default. |
| 5 | **organization_adhoc_filename**  | Specifies the filename of organization_adhoc. Used as an override for the JSON. Has no default. |
