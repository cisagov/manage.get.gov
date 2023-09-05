from registrar.models.public_contact import PublicContact

# TODO - dataclass?
class EppHelper:
    """ Helper function for data returned from EppLib """
    class EppObject(object):
        """Used to simplify dealing with returned Epp objects.
        Does not do type checking, and is not a model."""
        def __init__(
            self,
            auth_info=...,
            contacts=...,
            cr_date=...,
            ex_date=...,
            hosts=...,
            name=...,
            registrant=...,
            statuses=...,
            tr_date=...,
            avail=...,
            email=...,
            **kwargs
        ):
            self.auth_info = auth_info
            self.contacts = contacts
            self.cr_date = cr_date
            self.ex_date = ex_date
            self.hosts = hosts
            self.name = name
            self.registrant = registrant
            self.statuses = statuses
            self.tr_date = tr_date
            self.avail = avail
            self.fields = kwargs
            self.email = email

    # TODO - replace with PublicContact
    class EppContact:
        """Used to simplify dealing with returned Epp contacts.
        Does not do type checking, and is not a model."""
        def __init__(
            self,
            registry_id=...,
            auth_info=...,
            cr_date=...,
            tr_date=...,
            disclose=...,
            email=...,
            fax=...,
            postal_info=...,
            statuses=...,
            voice=...,
            **kwargs
        ):
            self.registry_id = registry_id
            self.auth_info = auth_info
            self.cr_date = cr_date
            self.tr_date = tr_date
            self.disclose = disclose
            self.email = email
            self.fax = fax
            self.postal_info = postal_info
            self.statuses = statuses
            self.voice = voice

        # TODO - in progress
        def map_to_public_contact(self, contact_type: PublicContact.ContactTypeChoices):
            """Maps the EppContact Object to a PublicContact object"""
            return PublicContact(
                contact_type=contact_type,
                registry_id=self.registry_id,
                email=self.email,
                voice=self.voice,
                fax=self.fax,
                # TODO - need the structure of auth_info
                pw=self.auth_info,
            )
