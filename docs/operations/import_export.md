# Export / Import Tables

A means is provided to export and import tables from
one environment to another. This allows for replication of
production data in a development environment. Import and export
are provided through a modified library, django-import-export.
Simple scripts are provided as detailed below.

### Export

To export from the source environment, run the following command from src directory:
manage.py export_tables

This exports a file, exported_tables.zip, to the tmp directory

For reference, the zip file will contain the following tables in csv form:

* User
* Contact
* Domain
* DomainRequest
* DomainInformation
* DomainUserRole
* DraftDomain
* Websites
* Host
* HostIP

After exporting the file from the target environment, scp the exported_tables.zip
file from the target environment to local.

Get passcode by running:
cf ssh-code

scp file from app (app is getgov-stable in example below) to local cwd:
scp -P 2222 -o User=cf:$(cf curl /v3/apps/$(cf app getgov-stable --guid)/processes | jq -r '.resources[] | select(.type=="web") | .guid')/0 ssh.fr.cloud.gov:app/tmp/exported_tables.zip .
when prompted, supply the passcode retrieved in the 'cf ssh-code' command


### Import

When importing into the target environment, if the target environment
is different than the source environment, it must be prepared for the
import. This involves clearing out rows in the appropriate tables so
that there are no database conflicts on import.

#### Preparing Target Environment

In order to delete all rows from the appropriate tables, run the following
command:
manage.py clean_tables

For reference, this deletes all rows from the following tables:

* DomainInformation
* DomainRequest
* Domain
* User (all but the current user)
* Contact
* Websites
* DraftDomain
* HostIP
* Host

#### Importing into Target Environment

Once target environment is prepared, files can be imported.

To scp the exported_tables.zip file from local to the sandbox, run the following:

Get passcode by running:
cf ssh-code

scp file from app (app is getgov-stable in example below) to local cwd:
scp -P 2222 -o User=cf:$(cf curl /v3/apps/$(cf app getgov-stable --guid)/processes | jq -r '.resources[] | select(.type=="web") | .guid')/0 tmp/exported_tables.zip ssh.fr.cloud.gov:app/tmp/exported_tables.zip
when prompted, supply the passcode retrieved in the 'cf ssh-code' command

Then connect to a shell in the target environment, and run the following import command:
manage.py import_tables

For reference, this imports tables in the following order:

* User
* Contact
* Domain
* Host
* HostIP
* DraftDomain
* Websites
* DomainRequest
* DomainInformation
* UserDomainRole

Optional step:
* Run fixtures to load fixture users back in