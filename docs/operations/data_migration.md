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

Transferring this data from these files into our domain tables happens in two steps;

***IMPORTANT: only run the following locally, to avoid publicizing PII in our public repo.***

### STEP 1: Load Transition Domain data into TransitionDomain table

**SETUP**
In order to use the management command, we need to add the files to a folder under `src/`.
This will allow Docker to mount the files to a container (under `/app`) for our use.  

 - Create a folder called `tmp` underneath `src/`
 - Add the above files to this folder
 - Open a terminal and navigate to `src/`

Then run the following command  (This will parse the three files in your `tmp` folder and load the information into the TransitionDomain table);
```shell
docker compose run -T app ./manage.py load_transition_domain /app/tmp/escrow_domain_contacts.daily.gov.GOV.txt /app/tmp/escrow_contacts.daily.gov.GOV.txt /app/tmp/escrow_domain_statuses.daily.gov.GOV.txt
```

**OPTIONAL COMMAND LINE ARGUMENTS**: 
`--debug`
This will print out additional, detailed logs.

`--limitParse 100` 
Directs the script to load only the first 100 entries into the table.  You can adjust this number as needed for testing purposes.  

`--resetTable`
This will delete all the data loaded into transtion_domain.  It is helpful if you want to see the entries reload from scratch or for clearing test data.


### STEP 2: Transfer Transition Domain data into main Domain tables

Now that we've loaded all the data into TransitionDomain, we need to update the main Domain and DomainInvitation tables with this information.  

In the same terminal as used in STEP 1, run the command below; 
(This will parse the data in TransitionDomain and either create a corresponding Domain object, OR, if a corresponding Domain already exists, it will update that Domain with the incoming status. It will also create DomainInvitation objects for each user associated with the domain):
```shell
docker compose run -T app ./manage.py transfer_transition_domains_to_domains
```

**OPTIONAL COMMAND LINE ARGUMENTS**: 
`--debug`
This will print out additional, detailed logs.

`--limitParse 100` 
Directs the script to load only the first 100 entries into the table.  You can adjust this number as needed for testing purposes.  