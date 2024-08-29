# Registrar Data Migration

The original system uses an existing registrar/registry that we will import.
The company of that system will provide us with an export of the existing data.
The goal of our data migration is to take the provided data and use
it to create, as close as possible, a _matching_ state
in our registrar.

There is no way to make our registrar _identical_ to the original system
because we have a different data model and workflow model. Instead, we should
focus our migration efforts on creating a state in our new registrar that will
primarily allow users of the system to perform the tasks that they want to do.

#### Users

One of the major differences with the existing registrar/registry is that our
system uses Login.gov for authentication. Any person with an identity-verified
Login.gov account can make an account on the new registrar. The first time
a person logs into the registrar through Login.gov, we make a corresponding 
account in our user table. Because we cannot know the Universal Unique ID (UUID) 
for a person's Login.gov account, we cannot pre-create user accounts for 
individuals in our new registrar based on the original data.

#### Domains

Our registrar keeps track of domains. The authoritative source for domain
information is the registry, but the registrar needs a copy of that
information to make connections between registry users and the domains that
they manage. The registrar stores very few fields about a domain except for
its name, so it could be straightforward to import the exported list of domains
from `escrow_domains.daily.dotgov.GOV.txt`. It doesn't appear that
that table stores a flag for if a domain is active or inactive.

An example Django management command that can load the delimited text file
from the daily escrow is in
`src/registrar/management/commands/load_domains_data.py`. It uses Django's
object-relational modeler (ORM) to create Django objects for the domains and
then write them to the database in a single bulk operation. To run the command
locally for testing, using Docker Compose:

```shell
docker compose run -T app ./manage.py load_domains_data < /tmp/escrow_domains.daily.dotgov.GOV.txt
```

#### User access to domains

The data export contains a `escrow_domain_contacts.daily.dotgov.txt` file
that links each domain to three different types of contacts: `billing`,
`tech`, and `admin`. The ID of the contact in this linking table corresponds
to the ID of a contact in the `escrow_contacts.daily.dotgov.txt` file. The
contacts file contains an email address for each contact.

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

## Set Up Files for Importing Domains

### Step 1: Obtain migration data files
We are provided with information about Transition Domains in the following files:
|  | Filename                                    | Description |  
|:-| :-------------------------------------------- | :---------- |
|1| **escrow_domain_contacts.daily.gov.GOV.txt**  | Has the map of domain names to contact ID. Domains in this file will usually have 3 contacts each
|2| **escrow_contacts.daily.gov.GOV.txt**         | Has the mapping of contact id to contact email address (which is what we care about for sending domain invitations)
|3| **escrow_domain_statuses.daily.gov.GOV.txt**  | Has the map of domains and their statuses
|4| **escrow_domains.daily.dotgov.GOV.txt**       | Has a map of domainname, expiration and creation dates
|5| **domainadditionaldatalink.adhoc.dotgov.txt** | Has the map of domains to other data like authority, organization, & domain type
|6| **domaintypes.adhoc.dotgov.txt**              | Has data on federal type and organization type
|7| **organization.adhoc.dotgov.txt**             | Has organization name data
|8| **authority.adhoc.dotgov.txt**                | Has authority data which maps to an agency
|9| **agency.adhoc.dotgov.txt**                   | Has federal agency data
|10| **migrationFilepaths.json**                  | A JSON which points towards all given filenames. Specified below.

### Step 2: Obtain JSON file for migration files locations
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

### Step 3: Bundle all relevant data files into an archive
Move all the files specified in Step 1 into a shared folder, and create a tar.gz.

Create a folder on your desktop called `datafiles` and move all of the obtained files into that. Add these files to a tar.gz archive using any method. See [here](https://stackoverflow.com/questions/53283240/how-to-create-tar-file-with-7zip).

After this is created, move this archive into `src/migrationdata`.


### Set Up Migrations on Sandbox
Load migration data onto a production or sandbox environment

**WARNING:** All files uploaded in this manner are temporary, i.e. they will be deleted when the app is restaged.
Do not use these environments to store data you want to keep around permanently. We don't want sensitive data to be accidentally present in our application environments.

### Step 1: Transfer data to sandboxes
Use the following cat command to upload your data to a sandbox environment of your choice:

```bash
cat {LOCAL_PATH_TO_FILE} | cf ssh {APP_NAME_IN_ENVIRONMENT} -c "cat > /home/vcap/tmp/{DESIRED_NAME_OF_FILE}"
```

* APP_NAME_IN_ENVIRONMENT - Name of the app running in your environment, e.g. getgov-za or getgov-stable
* LOCAL_PATH_TO_FILE - Path to the file you want to copy, ex: src/tmp/escrow_contacts.daily.gov.GOV.txt
* DESIRED_NAME_OF_FILE - Use this to specify the filename and type, ex: test.txt or escrow_contacts.daily.gov.GOV.txt

#### TROUBLESHOOTING STEP 1 ISSUES 
Depending on your operating system (Windows for instance), this command may upload corrupt data. If you encounter the error `gzip: prfiles.tar.gz: not in gzip format` when trying to unzip a .tar.gz file, use the scp command instead.

**IMPORTANT:** Only follow the below troubleshooting steps if cat does not work as expected. If it does, skip to step 2.
<details>
<summary>Troubleshooting cat instructions 
</summary>
    
#### Use scp to transfer data to sandboxes. 
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
</details>


### Step 2: Transfer uploaded files to the getgov directory
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
./manage.py cat_files_into_getgov --file_extension {FILE_EXTENSION_TYPE}
```

This will look for all files in /tmp with that are the same file type as `FILE_EXTENSION_TYPE`. 

**Example 1: Transferring txt files**

`./manage.py cat_files_into_getgov --file_extension txt` will search for
all files with the .txt extension.

**Example 2: Transferring tar.gz files**

`./manage.py cat_files_into_getgov --file_extension tar.gz` will search 
for .tar.gz files.

If you are using a tar.gz file, you will need to perform one additional step to extract it.
Run the following command from the same directory:
```shell
tar -xvf migrationdata/{FILE_NAME}.tar.gz -C migrationdata/ --strip-components=1
```

*FILE_NAME* - Name of the desired file, ex: exportdata


#### Manually transferring your files
If the `cat_files_into_getgov.py` script isn't working, follow these steps instead.

##### Move the desired file into the correct directory

```shell
cat ../tmp/{filename} > migrationdata/{filename}
```


*You are now ready to run migration scripts (see [Running the Domain Migration Scripts](running-the-domain-migration-scripts))*

### Set Up Local Migrations (TESTING PURPOSES ONLY)

***IMPORTANT: only use test data, to avoid publicizing PII in our public repo.***

In order to run the scripts locally, we need to add the files to a folder under `src/`.
This will allow Docker to mount the files to a container (under `/app`) for our use.  

 - Add the same files from section 1 to a TEMPORARY `tmp/` folder under `src/` (do not check this folder into our repo)
 - Open a terminal and navigate to `src/`


*You are now ready to run migration scripts.*

## Running the Domain Migration Scripts
While keeping the same ssh instance open (if you are running on a sandbox), run through the following commands. If you cannot run `manage.py` commands, try running `/tmp/lifecycle/shell` in the ssh instance. 

### Step 1: Upload Transition Domains

Run the following command, making sure the file paths point to the right location of your migration files. This will parse all given files and 
load the information into the TransitionDomain table. Make sure you have your migrationFilepaths.json file in the same directory.

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
**Note:** `--limitParse` is currently experiencing issues and may not work as intended.

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

### Step 2: Transfer Transition Domain data into main Domain tables

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
**Note:** `--limitParse` is currently experiencing issues and may not work as intended.

### Step 3: Send Domain invitations

To send invitation emails for every transition domain in the transition domain table, execute the following command:

##### LOCAL COMMAND
```shell
docker compose run -T app ./manage.py send_domain_invitations -s
```
##### SANDBOX COMMAND
```shell
./manage.py send_domain_invitations -s
```

### Step 4: Test the results (Run the analyzer script)

This script's main function is to scan the transition domain and domain tables for any anomalies.  It produces a simple report of missing or duplicate data.  NOTE: some missing data might be expected depending on the nature of our migrations so use best judgement when evaluating the results.

#### OPTION 1 - Analyze Only

To analyze our database without running migrations, execute the script without any optional arguments:

##### LOCAL COMMAND
```shell
docker compose run -T app ./manage.py master_domain_migrations --debug
```
##### SANDBOX COMMAND
```shell
./manage.py master_domain_migrations --debug
```

#### OPTION 2 - Run Migrations Feature

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
purposes.
**Note:** `--limitParse` is currently experiencing issues and may not work as intended.

`--resetTable`

Used by the migration scripts to trigger a prompt for deleting all table entries.  
Useful for testing purposes, but *use with caution*

## Import organization data
During MVP, our import scripts did not populate the following fields: `address_line, city, state_territory, and zipcode` for organization address in Domain Information. This was primarily due to time constraints. Because of this, we need to run a follow-on script to load this remaining data on each `DomainInformation` object.

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
| 3 | **directory**                    | Specifies the directory containing the files that will be parsed. Defaults to "migrationdata" |
| 4 | **domain_additional_filename**   | Specifies the filename of domain_additional. Used as an override for the JSON. Has no default. |
| 5 | **organization_adhoc_filename**  | Specifies the filename of organization_adhoc. Used as an override for the JSON. Has no default. |


## Extend Domain Extension Dates
This section outlines how to extend the expiration date of all ready domains (or a select subset) by a defined period of time. 

### Running on sandboxes

#### Step 1: Login to CloudFoundry
```cf login -a api.fr.cloud.gov --sso```

#### Step 2: SSH into your environment
```cf ssh getgov-{space}```

Example: `cf ssh getgov-za`

#### Step 3: Create a shell instance
```/tmp/lifecycle/shell```

#### Step 4: Extend domains
```./manage.py extend_expiration_dates```

### Running locally
```docker-compose exec app ./manage.py extend_expiration_dates```

##### Optional parameters
|   | Parameter                  | Description                                                                 |
|:-:|:-------------------------- |:----------------------------------------------------------------------------|
| 1 | **extensionAmount**        | Determines the period of time to extend by, in years. Defaults to 1 year.   |
| 2 | **debug**                  | Increases logging detail. Defaults to False.                                |
| 3 | **limitParse**             | Determines how many domains to parse. Defaults to all.                      |
| 4 | **disableIdempotentCheck** | Boolean that determines if we should check for idempotence or not. Compares the proposed extension date to the value in TransitionDomains. Defaults to False. |


## Populate First Ready
This section outlines how to run the populate_first_ready script

### Running on sandboxes

#### Step 1: Login to CloudFoundry
```cf login -a api.fr.cloud.gov --sso```

#### Step 2: SSH into your environment
```cf ssh getgov-{space}```

Example: `cf ssh getgov-za`

#### Step 3: Create a shell instance
```/tmp/lifecycle/shell```

#### Step 4: Running the script
```./manage.py populate_first_ready --debug```

### Running locally
```docker-compose exec app ./manage.py populate_first_ready --debug```

##### Optional parameters
|   | Parameter                  | Description                                                                 |
|:-:|:-------------------------- |:----------------------------------------------------------------------------|
| 1 | **debug**                  | Increases logging detail. Defaults to False.                                |


## Patch Federal Agency Info
This section outlines how to use `patch_federal_agency_info.py`

### Running on sandboxes

#### Step 1: Grab the latest `current-full.csv` file from the dotgov-data repo
Download the csv from [here](https://github.com/cisagov/dotgov-data/blob/main/current-full.csv) and place this file under the `src/migrationdata/` directory.

#### Step 2: Transfer the `current-full.csv` file to your sandbox
[Click here to go to the section about transferring data to sandboxes](#step-1-transfer-data-to-sandboxes)

#### Step 3: Login to CloudFoundry
```cf login -a api.fr.cloud.gov --sso```

#### Step 4: SSH into your environment
```cf ssh getgov-{space}```

Example: `cf ssh getgov-za`

#### Step 5: Create a shell instance
```/tmp/lifecycle/shell```

#### Step 6: Patch agency info
```./manage.py patch_federal_agency_info migrationdata/current-full.csv --debug```

### Running locally
```docker-compose exec app ./manage.py patch_federal_agency_info migrationdata/current-full.csv --debug```

##### Optional parameters
|   | Parameter                  | Description                                                                 |
|:-:|:-------------------------- |:----------------------------------------------------------------------------|
| 1 | **debug**                  | Increases logging detail. Defaults to False.                                |


## Populate Organization type
This section outlines how to run the `populate_organization_type` script. 
The script is used to update the organization_type field on DomainRequest and DomainInformation when it is None.
That data are synthesized from the generic_org_type field and the is_election_board field by concatenating " - Elections" on the end of generic_org_type string if is_elections_board is True.

### Running on sandboxes

#### Step 1: Login to CloudFoundry
```cf login -a api.fr.cloud.gov --sso```

#### Step 2: Get the domain_election_board file
The latest domain_election_board csv can be found [here](https://drive.google.com/file/d/1aDeCqwHmBnXBl2arvoFCN0INoZmsEGsQ/view).
After downloading this file, place it in `src/migrationdata`

#### Step 3: Upload the domain_election_board file to your sandbox
Follow [Step 1: Transfer data to sandboxes](#step-1-transfer-data-to-sandboxes) and [Step 2: Transfer uploaded files to the getgov directory](#step-2-transfer-uploaded-files-to-the-getgov-directory) from the [Set Up Migrations on Sandbox](#set-up-migrations-on-sandbox) portion of this doc.

#### Step 4: SSH into your environment
```cf ssh getgov-{space}```

Example: `cf ssh getgov-za`

#### Step 5: Create a shell instance
```/tmp/lifecycle/shell```

#### Step 6: Running the script
```./manage.py populate_organization_type {domain_election_board_filename}```

- The domain_election_board_filename file must adhere to this format:
    - example.gov\
    example2.gov\
    example3.gov

Example: 
`./manage.py populate_organization_type migrationdata/election-domains.csv`

### Running locally

#### Step 1: Get the domain_election_board file
The latest domain_election_board csv can be found [here](https://drive.google.com/file/d/1aDeCqwHmBnXBl2arvoFCN0INoZmsEGsQ/view).
After downloading this file, place it in `src/migrationdata`


#### Step 2: Running the script
```docker-compose exec app ./manage.py populate_organization_type {domain_election_board_filename}```

Example (assuming that this is being ran from src/): 
`docker-compose exec app ./manage.py populate_organization_type migrationdata/election-domains.csv`


### Required parameters
|   | Parameter                           | Description                                                        |
|:-:|:------------------------------------|:-------------------------------------------------------------------|
| 1 | **domain_election_board_filename** | A file containing every domain that is an election office.


## Populate Verification Type
This section outlines how to run the `populate_verification_type` script. 
The script is used to update the verification_type field on User when it is None.

### Running on sandboxes

#### Step 1: Login to CloudFoundry
```cf login -a api.fr.cloud.gov --sso```

#### Step 2: SSH into your environment
```cf ssh getgov-{space}```

Example: `cf ssh getgov-za`

#### Step 3: Create a shell instance
```/tmp/lifecycle/shell```

#### Step 4: Running the script
```./manage.py populate_verification_type```

### Running locally

#### Step 1: Running the script
```docker-compose exec app ./manage.py populate_verification_type```


## Copy names from contacts to users

### Running on sandboxes

#### Step 1: Login to CloudFoundry
```cf login -a api.fr.cloud.gov --sso```

#### Step 2: SSH into your environment
```cf ssh getgov-{space}```

Example: `cf ssh getgov-za`

#### Step 3: Create a shell instance
```/tmp/lifecycle/shell```

#### Step 4: Running the script
```./manage.py copy_names_from_contacts_to_users --debug```

### Running locally

#### Step 1: Running the script
```docker-compose exec app ./manage.py copy_names_from_contacts_to_users --debug```

##### Optional parameters
|   | Parameter                  | Description                                                                 |
|:-:|:-------------------------- |:----------------------------------------------------------------------------|
| 1 | **debug**                  | Increases logging detail. Defaults to False.                                |

## Transfer federal agency script
The transfer federal agency script adds the "federal_type" field on each associated DomainRequest, and uses that to populate the "federal_type" field on each FederalAgency.

**Important:** When running this script, note that data generated by our fixtures will be inaccurate (since we assign random data to them). Use real data on this script.
Do note that there is a check on record uniqueness. If two or more records do NOT have the same value for federal_type for any given federal agency, then the record is skipped. This protects against fixtures data when loaded with real data.

### Running on sandboxes

#### Step 1: Login to CloudFoundry
```cf login -a api.fr.cloud.gov --sso```

#### Step 2: SSH into your environment
```cf ssh getgov-{space}```

Example: `cf ssh getgov-za`

#### Step 3: Create a shell instance
```/tmp/lifecycle/shell```

#### Step 4: Running the script
```./manage.py transfer_federal_agency_type```

### Running locally

#### Step 1: Running the script
```docker-compose exec app ./manage.py transfer_federal_agency_type```

## Email current metadata report

### Running on sandboxes

#### Step 1: Login to CloudFoundry
```cf login -a api.fr.cloud.gov --sso```

#### Step 2: SSH into your environment
```cf ssh getgov-{space}```

Example: `cf ssh getgov-za`

#### Step 3: Create a shell instance
```/tmp/lifecycle/shell```

#### Step 4: Running the script
```./manage.py email_current_metadata_report --emailTo {desired email address}```

### Running locally

#### Step 1: Running the script
```docker-compose exec app ./manage.py email_current_metadata_report --emailTo {desired email address}```

##### Parameters
|   | Parameter                  | Description                                                                        |
|:-:|:-------------------------- |:-----------------------------------------------------------------------------------|
| 1 | **emailTo**                | Specifies where the email will be emailed. Defaults to help@get.gov on production. |

## Populate federal agency initials and FCEB
This script adds to the "is_fceb" and "initials" fields on the FederalAgency model. This script expects a CSV of federal CIOs to pull from, which can be sourced from [here](https://docs.google.com/spreadsheets/d/14oXHFpKyUXS5_mDWARPusghGdHCrP67jCleOknaSx38/edit?gid=479328070#gid=479328070). 

### Running on sandboxes

#### Step 1: Login to CloudFoundry
```cf login -a api.fr.cloud.gov --sso```

#### Step 2: SSH into your environment
```cf ssh getgov-{space}```

Example: `cf ssh getgov-za`

#### Step 3: Create a shell instance
```/tmp/lifecycle/shell```

#### Step 4: Upload your csv to the desired sandbox
[Follow these steps](#use-scp-to-transfer-data-to-sandboxes) to upload the federal_cio csv to a sandbox of your choice.

#### Step 5: Running the script
```./manage.py populate_federal_agency_initials_and_fceb {path_to_CIO_csv}```

### Running locally

#### Step 1: Running the script
```docker-compose exec app ./manage.py populate_federal_agency_initials_and_fceb {path_to_CIO_csv}```

##### Parameters
|   | Parameter                  | Description                                                                        |
|:-:|:-------------------------- |:-----------------------------------------------------------------------------------|
| 1 | **federal_cio_csv_path**   | Specifies where the federal CIO csv is                                             |

## Load senior official table
This script adds SeniorOfficial records to the related table based off of a CSV. This script expects a CSV of federal CIOs to pull from, which can be sourced from [here](https://docs.google.com/spreadsheets/d/14oXHFpKyUXS5_mDWARPusghGdHCrP67jCleOknaSx38/edit?gid=479328070#gid=479328070). 

### Running on sandboxes

#### Step 1: Login to CloudFoundry
```cf login -a api.fr.cloud.gov --sso```

#### Step 2: SSH into your environment
```cf ssh getgov-{space}```

Example: `cf ssh getgov-za`

#### Step 3: Create a shell instance
```/tmp/lifecycle/shell```

#### Step 4: Upload your csv to the desired sandbox
[Follow these steps](#use-scp-to-transfer-data-to-sandboxes) to upload the federal_cio csv to a sandbox of your choice.

#### Step 5: Running the script
```./manage.py load_senior_official_table {path_to_CIO_csv}```

### Running locally

#### Step 1: Running the script
```docker-compose exec app ./manage.py load_senior_official_table {path_to_CIO_csv}```

##### Parameters
|   | Parameter                  | Description                                                                        |
|:-:|:-------------------------- |:-----------------------------------------------------------------------------------|
| 1 | **federal_cio_csv_path**   | Specifies where the federal CIO csv is                                             |

## Populate Domain Request Dates
This section outlines how to run the populate_domain_request_dates script

### Running on sandboxes

#### Step 1: Login to CloudFoundry
```cf login -a api.fr.cloud.gov --sso```

#### Step 2: SSH into your environment
```cf ssh getgov-{space}```

Example: `cf ssh getgov-za`

#### Step 3: Create a shell instance
```/tmp/lifecycle/shell```

#### Step 4: Running the script
```./manage.py populate_domain_request_dates```

### Running locally
```docker-compose exec app ./manage.py populate_domain_request_dates```

## Create federal portfolio
This script takes the name of a `FederalAgency` (like 'AMTRAK') and does the following:
1. Creates the portfolio record based off of data on the federal agency object itself
2. Creates suborganizations from existing DomainInformation records
3. Associates the SeniorOfficial record (if it exists)
4. Adds this portfolio to DomainInformation / DomainRequests or both

### Running on sandboxes

#### Step 1: Login to CloudFoundry
```cf login -a api.fr.cloud.gov --sso```

#### Step 2: SSH into your environment
```cf ssh getgov-{space}```

Example: `cf ssh getgov-za`

#### Step 3: Create a shell instance
```/tmp/lifecycle/shell```

#### Step 4: Upload your csv to the desired sandbox
[Follow these steps](#use-scp-to-transfer-data-to-sandboxes) to upload the federal_cio csv to a sandbox of your choice.

#### Step 5: Running the script
```./manage.py create_federal_portfolio "{federal_agency_name}" --parse_requests --parse_domains```

Example: `./manage.py create_federal_portfolio "AMTRAK" --parse_requests --parse_domains`

### Running locally

#### Step 1: Running the script
```docker-compose exec app ./manage.py create_federal_portfolio "{federal_agency_name}" --parse_requests --parse_domains```

##### Parameters
|   | Parameter                  | Description                                                                                |
|:-:|:-------------------------- |:-------------------------------------------------------------------------------------------|
| 1 | **federal_agency_name**    | Name of the FederalAgency record surrounded by quotes. For instance,"AMTRAK".              |
| 2 | **parse_requests**         | Optional. If True, then the created portfolio is added to all related DomainRequests.      |
| 3 | **parse_domains**          | Optional. If True, then the created portfolio is added to all related Domains.             |

Note: While you can specify both at the same time, you must specify either --parse_requests or --parse_domains. You cannot run the script without defining one or the other.
