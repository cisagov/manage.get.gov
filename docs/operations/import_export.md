# Export / Import Tables

A means is provided to export and import individual tables from
one environment to another. This allows for replication of
production data in a development environment. Import and export
are provided through the django admin interface, through a modified
library, django-import-export. Each supported model has an Import
and an Export button on the list view.

### Export

When exporting models from the source environment, make sure that
no filters are selected. This will ensure that all rows of the model
are exported. Due to database dependencies, the following models 
need to be exported:

* User
* Contact
* Domain
* DomainRequest
* DomainInformation
* DomainUserRole
* DraftDomain
* Websites
* Host

### Import

When importing into the target environment, if the target environment
is different than the source environment, it must be prepared for the
import. This involves clearing out rows in the appropriate tables so
that there are no database conflicts on import.

#### Preparing Target Environment

Delete all rows from tables in the following order through django admin:

* DomainInformation
* DomainRequest
* Domain
* User (all but the current user)
* Contact
* Websites
* DraftDomain
* Host

#### Importing into Target Environment

Once target environment is prepared, files can be imported in the following
order:

* User (After importing User table, you need to delete all rows from Contact table before importing Contacts)
* Contact
* Host
* DraftDomain
* Websites
* Domain
* DomainRequest
* DomainInformation
* UserDomainRole