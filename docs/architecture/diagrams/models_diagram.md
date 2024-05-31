# Complete model documentation

This is an auto-generated diagram of our data models generated with the
[django-model2puml](https://github.com/sen-den/django-model2puml) library
using the command

```bash
$ docker compose exec app ./manage.py generate_puml --include registrar
```
Note: You must uncomment `puml_generator` from  `INSTALLED_APPS` in settings.py and docker-compose down and up before running the above command
![Complete data models diagram](./models_diagram.svg)

<details>
<summary>PlantUML source code</summary>

To regenerate this image using Docker, run

```bash
$ docker run -v $(pwd):$(pwd) -w $(pwd) -it plantuml/plantuml -tsvg models_diagram.md
```

```plantuml
@startuml 
class "registrar.Contact <Registrar>" as registrar.Contact #d6f4e9 {
    contact
    --
    + id (BigAutoField)
    + created_at (DateTimeField)
    + updated_at (DateTimeField)
    ~ user (OneToOneField)
    + first_name (TextField)
    + middle_name (TextField)
    + last_name (TextField)
    + title (TextField)
    + email (TextField)
    + phone (PhoneNumberField)
    --
}
registrar.Contact -- registrar.User


class "registrar.DomainRequest <Registrar>" as registrar.DomainRequest #d6f4e9 {
    domain request
    --
    + id (BigAutoField)
    + created_at (DateTimeField)
    + updated_at (DateTimeField)
    + status (FSMField)
    ~ creator (ForeignKey)
    ~ investigator (ForeignKey)
    + organization_type (CharField)
    + federally_recognized_tribe (BooleanField)
    + state_recognized_tribe (BooleanField)
    + tribe_name (TextField)
    + federal_agency (TextField)
    + federal_type (CharField)
    + is_election_board (BooleanField)
    + organization_name (TextField)
    + address_line1 (TextField)
    + address_line2 (CharField)
    + city (TextField)
    + state_territory (CharField)
    + zipcode (CharField)
    + urbanization (TextField)
    + type_of_work (TextField)
    + more_organization_information (TextField)
    ~ authorizing_official (ForeignKey)
    ~ approved_domain (OneToOneField)
    ~ requested_domain (OneToOneField)
    ~ submitter (ForeignKey)
    + purpose (TextField)
    + no_other_contacts_rationale (TextField)
    + anything_else (TextField)
    + is_policy_acknowledged (BooleanField)
    # current_websites (ManyToManyField)
    # alternative_domains (ManyToManyField)
    # other_contacts (ManyToManyField)
    --
}
registrar.DomainRequest -- registrar.User
registrar.DomainRequest -- registrar.User
registrar.DomainRequest -- registrar.Contact
registrar.DomainRequest -- registrar.DraftDomain
registrar.DomainRequest -- registrar.Domain
registrar.DomainRequest -- registrar.Contact
registrar.DomainRequest *--* registrar.Website
registrar.DomainRequest *--* registrar.Website
registrar.DomainRequest *--* registrar.Contact


class "registrar.DomainInformation <Registrar>" as registrar.DomainInformation #d6f4e9 {
    domain information
    --
    + id (BigAutoField)
    + created_at (DateTimeField)
    + updated_at (DateTimeField)
    ~ creator (ForeignKey)
    ~ domain_request (OneToOneField)
    + organization_type (CharField)
    + federally_recognized_tribe (BooleanField)
    + state_recognized_tribe (BooleanField)
    + tribe_name (TextField)
    + federal_agency (TextField)
    + federal_type (CharField)
    + is_election_board (BooleanField)
    + organization_name (TextField)
    + address_line1 (TextField)
    + address_line2 (CharField)
    + city (TextField)
    + state_territory (CharField)
    + zipcode (CharField)
    + urbanization (TextField)
    + type_of_work (TextField)
    + more_organization_information (TextField)
    ~ authorizing_official (ForeignKey)
    ~ domain (OneToOneField)
    ~ submitter (ForeignKey)
    + purpose (TextField)
    + no_other_contacts_rationale (TextField)
    + anything_else (TextField)
    + is_policy_acknowledged (BooleanField)
    + security_email (EmailField)
    # other_contacts (ManyToManyField)
    --
}
registrar.DomainInformation -- registrar.User
registrar.DomainInformation -- registrar.DomainRequest
registrar.DomainInformation -- registrar.Contact
registrar.DomainInformation -- registrar.Domain
registrar.DomainInformation -- registrar.Contact
registrar.DomainInformation *--* registrar.Contact


class "registrar.DraftDomain <Registrar>" as registrar.DraftDomain #d6f4e9 {
    draft domain
    --
    + id (BigAutoField)
    + created_at (DateTimeField)
    + updated_at (DateTimeField)
    + name (CharField)
    --
}


class "registrar.Domain <Registrar>" as registrar.Domain #d6f4e9 {
    domain
    --
    + id (BigAutoField)
    + created_at (DateTimeField)
    + updated_at (DateTimeField)
    + name (CharField)
    --
}


class "registrar.HostIP <Registrar>" as registrar.HostIP #d6f4e9 {
    host ip
    --
    + id (BigAutoField)
    + created_at (DateTimeField)
    + updated_at (DateTimeField)
    + address (CharField)
    ~ host (ForeignKey)
    --
}
registrar.HostIP -- registrar.Host


class "registrar.Host <Registrar>" as registrar.Host #d6f4e9 {
    host
    --
    + id (BigAutoField)
    + created_at (DateTimeField)
    + updated_at (DateTimeField)
    + name (CharField)
    ~ domain (ForeignKey)
    --
}
registrar.Host -- registrar.Domain


class "registrar.UserDomainRole <Registrar>" as registrar.UserDomainRole #d6f4e9 {
    user domain role
    --
    + id (BigAutoField)
    + created_at (DateTimeField)
    + updated_at (DateTimeField)
    ~ user (ForeignKey)
    ~ domain (ForeignKey)
    + role (TextField)
    --
}
registrar.UserDomainRole -- registrar.User
registrar.UserDomainRole -- registrar.Domain


class "registrar.DomainInvitation <Registrar>" as registrar.DomainInvitation #d6f4e9 {
    domain invitation
    --
    + id (BigAutoField)
    + created_at (DateTimeField)
    + updated_at (DateTimeField)
    + email (EmailField)
    ~ domain (ForeignKey)
    + status (FSMField)
    --
}
registrar.DomainInvitation -- registrar.Domain


class "registrar.Nameserver <Registrar>" as registrar.Nameserver #d6f4e9 {
    nameserver
    --
    + id (BigAutoField)
    + created_at (DateTimeField)
    + updated_at (DateTimeField)
    + name (CharField)
    ~ domain (ForeignKey)
    ~ host_ptr (OneToOneField)
    --
}
registrar.Nameserver -- registrar.Domain
registrar.Nameserver -- registrar.Host


class "registrar.PublicContact <Registrar>" as registrar.PublicContact #d6f4e9 {
    public contact
    --
    + id (BigAutoField)
    + created_at (DateTimeField)
    + updated_at (DateTimeField)
    + contact_type (CharField)
    + registry_id (CharField)
    ~ domain (ForeignKey)
    + name (TextField)
    + org (TextField)
    + street1 (TextField)
    + street2 (TextField)
    + street3 (TextField)
    + city (TextField)
    + sp (TextField)
    + pc (TextField)
    + cc (TextField)
    + email (TextField)
    + voice (TextField)
    + fax (TextField)
    + pw (TextField)
    --
}

registrar.PublicContact -- registrar.Domain


class "registrar.User <Registrar>" as registrar.User #d6f4e9 {
    user
    --
    + id (BigAutoField)
    + password (CharField)
    + last_login (DateTimeField)
    + is_superuser (BooleanField)
    + username (CharField)
    + first_name (CharField)
    + last_name (CharField)
    + email (EmailField)
    + is_staff (BooleanField)
    + is_active (BooleanField)
    + date_joined (DateTimeField)
    + phone (PhoneNumberField)
    # groups (ManyToManyField)
    # user_permissions (ManyToManyField)
    # domains (ManyToManyField)
    --
}
registrar.User *--* registrar.Domain


class "registrar.Website <Registrar>" as registrar.Website #d6f4e9 {
    website
    --
    + id (BigAutoField)
    + created_at (DateTimeField)
    + updated_at (DateTimeField)
    + website (CharField)
    --
}


@enduml
```

</details>
