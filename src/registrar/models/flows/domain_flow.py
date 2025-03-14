import logging

from django_fsm import TransitionNotAllowed
from registrar.models.domain import Domain
from registrar.models.public_contact import PublicContact
from viewflow import fsm
from django.utils import timezone
from epplibwrapper import RegistryError

logger = logging.getLogger(__name__)


class DomainFlow(object):
    """
    Controls the "flow" between states of the Domain object
    Only pass Domain to this class
    """

    state = fsm.State(Domain.State, default=Domain.State.UNKNOWN)

    def __init__(self, domain):
        self.domain = domain

    @state.setter()
    def _set_domain_state(self, value):
        self.domain.__dict__["state"] = value

    @state.getter()
    def _get_domain_state(self):
        return self.domain.state

    @state.transition(source=Domain.State.UNKNOWN, target=Domain.State.DNS_NEEDED)
    def dns_needed_from_unknown(self):
        logger.info("Changing to dns_needed")

        # Registrant must be created before the domain
        registrantID = self.domain.addRegistrant()

        # create the domain in the registry and add Public contacts
        self.domain._create_domain_in_registry(registrantID)
        self.domain.addAllDefaults()

    @state.transition(source=[Domain.State.READY, Domain.State.ON_HOLD], target=Domain.State.ON_HOLD)
    def place_client_hold(self, ignoreEPP=False):
        """place a clienthold on a domain (no longer should resolve)
        ignoreEPP (boolean) - set to true to by-pass EPP (used for transition domains)
        """

        # (check prohibited statuses)
        logger.info("clientHold()-> inside clientHold")

        # In order to allow transition domains to by-pass EPP calls,
        # include this ignoreEPP flag
        if not ignoreEPP:
            self.domain._place_client_hold()

    @state.transition(source=[Domain.State.READY, Domain.State.ON_HOLD], target=Domain.State.READY)
    def revert_client_hold(self, ignoreEPP=False):
        """undo a clienthold placed on a domain
        ignoreEPP (boolean) - set to true to by-pass EPP (used for transition domains)
        """

        logger.info("clientHold()-> inside clientHold")
        if not ignoreEPP:
            self.domain._remove_client_hold()

    @state.transition(source=[Domain.State.ON_HOLD, Domain.State.DNS_NEEDED], target=Domain.State.DELETED)
    def deletedInEpp(self):
        """Domain is deleted in epp but is saved in our database.
        Subdomains will be deleted first if not in use by another domain.
        Contacts for this domain will also be deleted.
        Error handling should be provided by the caller."""
        # While we want to log errors, we want to preserve
        # that information when this function is called.
        # Human-readable errors are introduced at the admin.py level,
        # as doing everything here would reduce reliablity.
        try:
            logger.info("deletedInEpp()-> inside _delete_domain")
            self.domain._delete_domain()
            self.domain.deleted = timezone.now()
            self.domain.expiration_date = None
        except RegistryError as err:
            logger.error(f"Could not delete domain. Registry returned error: {err}. {err.note}")
            raise err
        except TransitionNotAllowed as err:
            logger.error("Could not delete domain. FSM failure: {err}")
            raise err
        except Exception as err:
            logger.error(f"Could not delete domain. An unspecified error occured: {err}")
            raise err
        else:
            self.domain._invalidate_cache()

    @state.transition(
        source=[Domain.State.DNS_NEEDED, Domain.State.READY],
        target=Domain.State.READY,
        # conditions=[dns_not_needed]
    )
    def ready(self):
        """Transition to the ready state
        domain should have nameservers and all contacts
        and now should be considered live on a domain
        """
        logger.info("Changing to ready state")
        logger.info("able to transition to ready state")
        # if self.first_ready is not None, this means that this
        # domain was READY, then not READY, then is READY again.
        # We do not want to overwrite first_ready.
        if self.domain.first_ready is None:
            self.domain.first_ready = timezone.now()

    @state.transition(
        source=[Domain.State.READY],
        target=Domain.State.DNS_NEEDED,
    )
    def dns_needed(self):
        """Transition to the DNS_NEEDED state
        domain should NOT have nameservers but
        SHOULD have all contacts
        Going to check nameservers and will
        result in an EPP call
        """
        logger.info("Changing to DNS_NEEDED state")
        logger.info("able to transition to DNS_NEEDED state")

    @state.transition(source=Domain.State.UNKNOWN, target=Domain.State.DNS_NEEDED)
    def _add_missing_contacts_if_unknown(self, cleaned):
        """
        _add_missing_contacts_if_unknown: Add contacts (SECURITY, TECHNICAL, and/or ADMINISTRATIVE)
        if they are missing, AND switch the state to DNS_NEEDED from UNKNOWN (if it
        is in an UNKNOWN state, that is an error state)
        Note: The transition state change happens at the end of the function
        """

        missingAdmin = True
        missingSecurity = True
        missingTech = True

        contacts = cleaned.get("_contacts", [])
        if len(contacts) < 3:
            for contact in contacts:
                if contact.type == PublicContact.ContactTypeChoices.ADMINISTRATIVE:
                    missingAdmin = False
                if contact.type == PublicContact.ContactTypeChoices.SECURITY:
                    missingSecurity = False
                if contact.type == PublicContact.ContactTypeChoices.TECHNICAL:
                    missingTech = False

            # We are only creating if it doesn't exist so we don't overwrite
            if missingAdmin:
                administrative_contact = self.domain.get_default_administrative_contact()
                administrative_contact.save()
            if missingSecurity:
                security_contact = self.domain.get_default_security_contact()
                security_contact.save()
            if missingTech:
                technical_contact = self.domain.get_default_technical_contact()
                technical_contact.save()

            logger.info(
                "_add_missing_contacts_if_unknown => Adding contacts. Values are "
                f"missingAdmin: {missingAdmin}, missingSecurity: {missingSecurity}, missingTech: {missingTech}"
            )
