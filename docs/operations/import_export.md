# Export / Import Tables

A means is provided to export and import tables from
one environment to another. This allows for replication of
production data in a development environment. Import and export
are provided through a modified library, django-import-export.
Simple scripts are provided as detailed below.

### Export

To export from the source environment, run the following command from src directory:
manage.py export_tables

Connect to the source sandbox and run the command:
cf ssh {source-app}
/tmp/lifecycle/shell
./manage.py export_tables

example exporting from getgov-stable:
cf ssh getgov-stable
/tmp/lifecycle/shell
./manage.py export_tables

This exports a file, exported_tables.zip, to the tmp directory

For reference, the zip file will contain the following tables in csv form:

* User
* Contact
* Domain
* DomainRequest
* DomainInformation
* DomainUserRole
* DraftDomain
* FederalAgency
* Websites
* Host
* HostIP
* PublicContact

After exporting the file from the target environment, scp the exported_tables.zip
file from the target environment to local.  Run the below commands from local.

Get passcode by running:
cf ssh-code

scp file from source app to local file:
scp -P 2222 -o User=cf:$(cf curl /v3/apps/$(cf app {source-app} --guid)/processes | jq -r '.resources[] | select(.type=="web") | .guid')/0 ssh.fr.cloud.gov:app/tmp/exported_tables.zip {local_file_path}
when prompted, supply the passcode retrieved in the 'cf ssh-code' command

example copying from stable to local cwd:
scp -P 2222 -o User=cf:$(cf curl /v3/apps/$(cf app getgov-stable --guid)/processes | jq -r '.resources[] | select(.type=="web") | .guid')/0 ssh.fr.cloud.gov:app/tmp/exported_tables.zip .


### Import

When importing into the target environment, if the target environment
is different than the source environment, it must be prepared for the
import. This involves clearing out rows in the appropriate tables so
that there are no database conflicts on import.

#### Preparing Target Environment

In order to delete all rows from the appropriate tables, run the following
command:
cf ssh {target-app}
/tmp/lifecycle/shell
./manage.py clean_tables

example cleaning getgov-backup:
cf ssh getgov-backup
/tmp/lifecycle/backup
./manage.py clean_tables

For reference, this deletes all rows from the following tables:

* DomainInformation
* DomainRequest
* Domain
* User
* Contact
* Websites
* DraftDomain
* HostIP
* Host
* PublicContact
* FederalAgency

#### Importing into Target Environment

Once target environment is prepared, files can be imported.

If importing tables from stable environment into an OT&E sandbox, there will be a difference
between the stable's registry and the sandbox's registry. Therefore, you need to run import_tables
with --skipEppSave option set to False. If you set to False, it will attempt to save PublicContact
records to the registry on load. If this is unset, or set to True, it will load the database and not
attempt to update the registry on load.

To scp the exported_tables.zip file from local to the sandbox, run the following:

Get passcode by running:
cf ssh-code

scp file from local to target app:
scp -P 2222 -o User=cf:$(cf curl /v3/apps/$(cf app {target-app} --guid)/processes | jq -r '.resources[] | select(.type=="web") | .guid')/0 {local_file_path} ssh.fr.cloud.gov:app/tmp/exported_tables.zip
when prompted, supply the passcode retrieved in the 'cf ssh-code' command

example copy of local file in tmp to getgov-backup:
scp -P 2222 -o User=cf:$(cf curl /v3/apps/$(cf app getgov-backup --guid)/processes | jq -r '.resources[] | select(.type=="web") | .guid')/0 tmp/exported_tables.zip ssh.fr.cloud.gov:app/tmp/exported_tables.zip


Then connect to a shell in the target environment, and run the following import command:
cf ssh {target-app}
/tmp/lifecycle/shell
./manage.py import_tables

example cleaning getgov-backup:
cf ssh getgov-backup
/tmp/lifecycle/backup
./manage.py import_tables --no-skipEppSave

For reference, this imports tables in the following order:

* User
* Contact
* Domain
* Host
* HostIP
* DraftDomain
* Websites
* FederalAgency
* DomainRequest
* DomainInformation
* UserDomainRole
* PublicContact

Optional step:
* Run fixtures to load fixture users back in