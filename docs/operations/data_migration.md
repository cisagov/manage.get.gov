# Registrar Data Migration

There is an existing registrar/registry at Verisign. They will provide us with an
export of the data from that system. The goal of our data migration is to take
the provided data and use it to create as much as possible a _matching_ state
in our registrar.

There is no way to make our registrar _identical_ to the Verisign system
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
in our new registrar based on the data from Verisign.

## Domains

Our registrar keeps track of domains. The authoritative source for domain
information is the registry, but the registrar needs a copy of that
information to make connections between registry users and the domains that
they manage. The registrar stores very few fields about a domain except for
its name, so it could be straightforward to import the exported list of domains
from Verisign's `escrow_domains.daily.dotgov.GOV.txt`. It doesn't appear that
that table stores a flag for active or inactive, so every domain in the file
can be imported into our system as `is_active=True`.

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

The Verisign data contains a `escrow_domain_contacts.daily.dotgov.txt` file
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
Verisign system, and they use the same email address with Login.gov, then they
will end up with access to the same domains in the new registrar that they
were associated with in the Verisign system.

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
