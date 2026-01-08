"""
Service for all EPP registry interactions.

This service handles external I/O with the EPP registry.

"""

import logging
from enum import Enum
from datetime import date
from typing import Dict, List, Optional
from urllib import response
from epplibwrapper import (
    CLIENT as registry,
    commands,
    common as epp,
    extensions,
    info as eppInfo,
    RegistryError,
    ErrorCode,
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from registrar.models.domain import Domain
    from registrar.models.public_contact import PublicContact

logger = logging.getLogger(__name__)


class EPPRegistryService:
    """
    Handles all interactions with the EPP registry.

    Methods in this service:
    - Make EPP calls via registry.send()
    - Transform EPP responses into Python data structures
    - NEVER touch the database
    - NEVER hold database transactions
    """

    class DomainStatus(str, Enum):
        """
        The status codes we can receive from the registry.

        These are detailed in RFC 5731 in section 2.3.
        https://www.rfc-editor.org/std/std69.txt
        """

        # Requests to delete the object MUST be rejected.
        CLIENT_DELETE_PROHIBITED = "clientDeleteProhibited"
        SERVER_DELETE_PROHIBITED = "serverDeleteProhibited"

        # DNS delegation information MUST NOT be published for the object.
        CLIENT_HOLD = "clientHold"
        SERVER_HOLD = "serverHold"

        # Requests to renew the object MUST be rejected.
        CLIENT_RENEW_PROHIBITED = "clientRenewProhibited"
        SERVER_RENEW_PROHIBITED = "serverRenewProhibited"

        # Requests to transfer the object MUST be rejected.
        CLIENT_TRANSFER_PROHIBITED = "clientTransferProhibited"
        SERVER_TRANSFER_PROHIBITED = "serverTransferProhibited"

        # Requests to update the object (other than to remove this status)
        # MUST be rejected.
        CLIENT_UPDATE_PROHIBITED = "clientUpdateProhibited"
        SERVER_UPDATE_PROHIBITED = "serverUpdateProhibited"

        # Delegation information has not been associated with the object.
        # This is the default status when a domain object is first created
        # and there are no associated host objects for the DNS delegation.
        # This status can also be set by the server when all host-object
        # associations are removed.
        INACTIVE = "inactive"

        # This is the normal status value for an object that has no pending
        # operations or prohibitions.  This value is set and removed by the
        # server as other status values are added or removed.
        OK = "ok"

        # A transform command has been processed for the object, but the
        # action has not been completed by the server.  Server operators can
        # delay action completion for a variety of reasons, such as to allow
        # for human review or third-party action.  A transform command that
        # is processed, but whose requested action is pending, is noted with
        # response code 1001.
        PENDING_CREATE = "pendingCreate"
        PENDING_DELETE = "pendingDelete"
        PENDING_RENEW = "pendingRenew"
        PENDING_TRANSFER = "pendingTransfer"
        PENDING_UPDATE = "pendingUpdate"

    # ============================================================================
    # Domain Operations
    # ============================================================================

    def fetch_domain_info(self, domain_name: str):
        """
        Fetch domain information from EPP registry.

        Returns:
            Raw EPP response object

        Raises:
            RegistryError: If EPP call fails
        """
        req = commands.InfoDomain(name=domain_name)
        response = registry.send(req, cleaned=True)
        return response

    def create_domain(self, domain_name: str, registrant_id: str) -> None:
        """
        Create a domain in the EPP registry.

        Raises:
            RegistryError: If EPP call fails (except OBJECT_EXISTS)
        """
        req = commands.CreateDomain(
            name=domain_name,
            registrant=registrant_id,
            auth_info=epp.DomainAuthInfo(pw="2fooBAR123fooBaz"),
        )

        try:
            registry.send(req, cleaned=True)
            logger.info(f"Created domain {domain_name} in registry")
        except RegistryError as err:
            if err.code != ErrorCode.OBJECT_EXISTS:
                logger.error(f"Failed to create domain {domain_name}: {err}")
                raise err
            logger.info(f"Domain {domain_name} already exists in registry")

    def delete_domain(self, domain_name: str) -> None:
        """
        Delete a domain from the EPP registry.

        Raises:
            RegistryError: If EPP call fails
        """
        req = commands.DeleteDomain(name=domain_name)
        registry.send(req, cleaned=True)

    def update_domain_hosts(self, domain_name: str, hosts_to_add: List[str], hosts_to_remove: List[str]) -> int:
        """
        Update domain hosts in the EPP registry.

        Returns:
            ErrorCode integer value
        """
        if not hosts_to_add and not hosts_to_remove:
            return ErrorCode.COMMAND_COMPLETED_SUCCESSFULLY

        try:
            updateReq = commands.UpdateDomain(name=domain_name, add=hosts_to_add, rem=hosts_to_remove)
            logger.info("update_domain_hosts()-> sending update domain req as %s" % updateReq)
            response = registry.send(updateReq, cleaned=True)
            return response.code
        except RegistryError as e:
            logger.error("Error update_domain_hosts, code was %s error was %s" % (e.code, e))
            return e.code

    def place_client_hold(self, domain_name: str) -> None:
        """
        Place a client hold on a domain in the EPP registry.

        Raises:
            RegistryError: If EPP call fails
        """

        req = commands.UpdateDomain(name=domain_name, add=[self.clientHoldStatus()])
        registry.send(req, cleaned=True)
        logger.info(f"Placed client hold on {domain_name}")

    def remove_client_hold(self, domain_name: str) -> None:
        """
        Remove a client hold from a domain in the EPP registry.

        Raises:
            RegistryError: If EPP call fails
        """
        req = commands.UpdateDomain(name=domain_name, rem=[self.clientHoldStatus()])
        registry.send(req, cleaned=True)
        logger.info(f"Removed client hold from {domain_name}")

    def is_domain_available(self, domain_name: str) -> bool:
        """Check if domain is available for registration in EPP registry."""
        req = commands.CheckDomain([domain_name.lower()])
        response = registry.send(req, cleaned=True)
        return response.res_data[0].avail

    def is_pending_delete(self, domain_name: str) -> bool:
        """Check if domain is in pendingDelete state."""
        try:
            info_req = commands.InfoDomain(domain_name.lower())
            info_response = registry.send(info_req, cleaned=True)
            # Ensure res_data exists and is not empty
            if info_response and info_response.res_data:
                # Use _extract_data_from_response bc it's same thing but jsonified
                domain_info = info_response.res_data[0]
                statuses = getattr(domain_info, "statuses", [])
                return "pendingDelete" in [str(s.state) for s in statuses]
        except RegistryError as err:
            if not err.is_connection_error():
                logger.info(f"Domain does not exist yet so it won't be in pending delete -- {err}")
                return False
            raise
        return False

    def is_not_deleted(self, domain_name: str) -> bool:
        """Check if domain exists in registry (not deleted)."""
        try:
            info_req = commands.InfoDomain(domain_name.lower())
            info_response = registry.send(info_req, cleaned=True)
            # No res_data implies likely deleted
            return bool(info_response and info_response.res_data)
        except RegistryError as err:
            if not err.is_connection_error():
                # 2303 = Object does not exist -> Domain is deleted
                if err.code == 2303 or err.code == ErrorCode.OBJECT_DOES_NOT_EXIST:
                    return False
                logger.info("Unexpected registry error while checking domain -- %s", err)
                return True
            raise

    def renew_domain(self, domain_name: str, current_exp_date, length: int, unit) -> date:
        """
        Renew domain in EPP registry.

        Returns:
            New expiration date from registry

        Raises:
            RegistryError: If renewal fails
        """

        request = commands.RenewDomain(name=domain_name, cur_exp_date=current_exp_date, period=epp.Period(length, unit))

        response = registry.send(request, cleaned=True)
        new_exp_date = response.res_data[0].ex_date
        logger.info(f"Renewed domain {domain_name}, new expiration: {new_exp_date}")
        return new_exp_date

    # ============================================================================
    # Contact Operations
    # ============================================================================

    def fetch_contacts(self, contact_data: List) -> Dict[str, Optional["PublicContact"]]:
        """
        Fetch contact information from EPP registry.

        Args:
            contact_data: List of DomainContact objects from EPP

        Returns:
            Dict mapping contact type to unsaved PublicContact objects

        Raises:
            RegistryError: If EPP calls fail (logged but not raised)
        """
        from registrar.models.public_contact import PublicContact

        choices = PublicContact.ContactTypeChoices
        contacts_dict: Dict[str, Optional["PublicContact"]] = {
            choices.ADMINISTRATIVE: None,
            choices.SECURITY: None,
            choices.TECHNICAL: None,
        }

        for domain_contact in contact_data:
            try:
                req = commands.InfoContact(id=domain_contact.contact)
                data = registry.send(req, cleaned=True).res_data[0]

                # Map EPP response to PublicContact object (unsaved)
                mapped_object = self._map_epp_contact_to_public_contact(
                    data, domain_contact.contact, domain_contact.type
                )

                contacts_dict[mapped_object.contact_type] = mapped_object
                logger.debug(f"Fetched contact {domain_contact.contact} from registry")

            except RegistryError as e:
                logger.error(f"Failed to fetch contact {domain_contact.contact}: {e}")
                # Continues processing other contacts

        return contacts_dict

    def fetch_contact_info(self, registry_id: str) -> eppInfo.InfoContactResultData:
        """
        Fetch detailed contact information from EPP registry.

        Args:
            registry_id: Registry ID of the contact

        Returns:
            EPP InfoContactResultData object

        Raises:
            RegistryError: If EPP call fails
        """
        try:
            req = commands.InfoContact(id=registry_id)
            response = registry.send(req, cleaned=True)
            return response.res_data[0]
        except RegistryError as error:
            logger.error(
                "Registry threw error for contact id %s, error code is %s, full error is %s",
                registry_id,
                error.code,
                error,
            )
            raise error

    def create_contact(self, contact: "PublicContact", domain: "Domain") -> int:
        """
        Create a contact in the EPP registry.

        Args:
            contact: PublicContact object with contact data

        Returns:
            ErrorCode integer value
        """
        create = commands.CreateContact(
            id=contact.registry_id,
            postal_info=domain._make_epp_contact_postal_info(contact),
            email=contact.email,
            voice=contact.voice,
            fax=contact.fax,
            auth_info=epp.ContactAuthInfo(pw="2fooBAR123fooBaz"),
        )  # type: ignore
        # security contacts should only show email addresses, for now
        create.disclose = domain._disclose_fields(contact)
        try:
            registry.send(create, cleaned=True)
            logger.info(f"Created contact {contact.registry_id} in registry")
            return ErrorCode.COMMAND_COMPLETED_SUCCESSFULLY
        except RegistryError as err:
            # don't throw an error if it is just saying this is a duplicate contact
            if err.code != ErrorCode.OBJECT_EXISTS:
                logger.error(
                    "Registry threw error for contact id %s"
                    " contact type is %s,"
                    " error code is\n %s"
                    " full error is %s",
                    contact.registry_id,
                    contact.contact_type,
                    err.code,
                    err,
                )
                # TODO - 433 Error handling here

            else:
                logger.warning(
                    "Registrar tried to create duplicate contact for id %s",
                    contact.registry_id,
                )
            return err.code

    def delete_contact(self, registry_id: str) -> int:
        """
        Delete a contact from the EPP registry.

        Returns:
            ErrorCode integer value
        """
        req = commands.DeleteContact(id=registry_id)
        try:
            registry.send(req, cleaned=True)
            logger.info(f"Deleted contact {registry_id} from registry")
            return ErrorCode.COMMAND_COMPLETED_SUCCESSFULLY
        except RegistryError as err:
            logger.error(f"Failed to delete contact {registry_id}: {err}")
            return err.code

    def update_contact(self, contact: "PublicContact", domain: "Domain") -> None:
        """
        Update an existing contact in EPP registry.

        Raises:
            RegistryError: If update fails
        """

        updateContact = commands.UpdateContact(
            id=contact.registry_id,
            postal_info=domain._make_epp_contact_postal_info(contact=contact),
            email=contact.email,
            voice=contact.voice,
            fax=contact.fax,
            auth_info=epp.ContactAuthInfo(pw="2fooBAR123fooBaz"),
        )

        updateContact.disclose = domain._disclose_fields(contact=contact)

        registry.send(updateContact, cleaned=True)
        logger.info(f"Updated contact {contact.registry_id}")

    def update_domain_contact(self, domain_name: str, contact_id: str, contact_type: str, remove: bool = False) -> None:
        """
        Add or remove a contact from a domain.

        Args:
            domain_name: Domain name
            contact_id: Contact registry ID
            contact_type: Contact type (admin, tech, etc)
            remove: If True, remove contact; if False, add contact

        Raises:
            RegistryError: If update fails
        """
        domainContact = epp.DomainContact(contact=contact_id, type=contact_type)

        if remove:
            updateDomain = commands.UpdateDomain(name=domain_name, rem=[domainContact])
        else:
            updateDomain = commands.UpdateDomain(name=domain_name, add=[domainContact])

        registry.send(updateDomain, cleaned=True)
        action = "Removed" if remove else "Added"
        logger.info(f"{action} contact {contact_id} ({contact_type}) for domain {domain_name}")

    def update_domain_registrant(self, domain_name: str, registrant_id: str) -> None:
        """
        Change the registrant contact on an existing domain.

        Raises:
            RegistryError: If update fails
        """
        updateDomain = commands.UpdateDomain(name=domain_name, registrant=registrant_id)

        registry.send(updateDomain, cleaned=True)
        logger.info(f"Updated registrant for domain {domain_name} to {registrant_id}")

    # ============================================================================
    # Host Operations
    # ============================================================================

    def fetch_hosts(self, host_data: List[str]) -> List[dict]:
        """
        Fetch host information from EPP registry.

        Args:
            host_names: List of host names to fetch

        Returns:
            List of dicts with keys: name, addrs, cr_date, statuses, tr_date, up_date

        Raises:
            RegistryError: If EPP calls fail (logged but not raised)
        """
        hosts = []
        for name in host_data:
            try:
                req = commands.InfoHost(name=name)
                data = registry.send(req, cleaned=True).res_data[0]
                host = {
                    "name": name,
                    "addrs": [item.addr for item in getattr(data, "addrs", [])],
                    "cr_date": getattr(data, "cr_date", ...),
                    "statuses": getattr(data, "statuses", ...),
                    "tr_date": getattr(data, "tr_date", ...),
                    "up_date": getattr(data, "up_date", ...),
                }

                hosts.append({k: v for k, v in host.items() if v is not ...})
            except RegistryError as e:
                logger.error(f"Failed to fetch host {name}: {e}")
        return hosts

    def create_host(self, hostname: str, ip_addresses: List[str]) -> int:
        """
        Create a host in the EPP registry.

        Returns:
            ErrorCode integer value
        """
        addrs = self._convert_ips(ip_addresses)
        request = commands.CreateHost(name=hostname, addrs=addrs)
        logger.info("EPP create_host()-> sending req as %s" % request)

        try:
            response = registry.send(request, cleaned=True)
            logger.info(f"Created host {hostname} in registry")
            return response.code
        except RegistryError as e:
            logger.error("Error epp create_host, code was %s error was %s" % (e.code, e))
            if e.code == ErrorCode.OBJECT_EXISTS:
                return e.code
            else:
                raise e

    def update_host(self, hostname: str, add_ips: List[str], remove_ips: List[str]) -> int:
        """
        Update host IP addresses in the EPP registry.

        Returns:
            ErrorCode integer value
        """
        if not add_ips and not remove_ips:
            return ErrorCode.COMMAND_COMPLETED_SUCCESSFULLY

        try:
            request = commands.UpdateHost(
                name=hostname,
                add=self._convert_ips(add_ips),
                rem=self._convert_ips(remove_ips),
            )
            logger.info("EPP update_host()-> sending req as %s" % request)
            response = registry.send(request, cleaned=True)
            logger.info(f"Updated host {hostname}")
            return response.code
        except RegistryError as e:
            logger.error("Error update_host, code was %s error was %s" % (e.code, e))
            raise e

    def delete_host(self, hostname: str) -> None:
        """
        Delete a host from the EPP registry.

        Raises:
            RegistryError: If EPP call fails (except OBJECT_ASSOCIATION_PROHIBITS_OPERATION)
        """
        try:
            deleteHostReq = commands.DeleteHost(name=hostname)
            registry.send(deleteHostReq, cleaned=True)
            logger.info("EPP delete_host()-> sending delete host req as %s" % deleteHostReq)
        except RegistryError as e:
            raise e

    # ============================================================================
    # Private Helper Methods
    # ============================================================================

    def clientHoldStatus(self):
        return epp.Status(state=self.DomainStatus.CLIENT_HOLD, description="", lang="en")

    def _extract_dnssec_data(self, response_extensions):
        """Extract DNSSEC data from EPP response extensions."""

        dnssec_data = None
        for extension in response_extensions:
            if isinstance(extension, extensions.DNSSECExtension):
                dnssec_data = extension
        return dnssec_data

    def _map_epp_contact_to_public_contact(
        self, contact_data: eppInfo.InfoContactResultData, contact_id: str, contact_type: str
    ) -> "PublicContact":
        """
        Map EPP contact data to PublicContact object (unsaved).

        This is a helper method that transforms EPP data structures
        into our Django model format.
        """
        postal_info = contact_data.postal_info
        addr = postal_info.addr if postal_info else None

        # Extract street addresses
        streets = {}
        if addr and addr.street:
            for i, street in enumerate(addr.street[:3], 1):
                streets[f"street{i}"] = street

        from registrar.models.public_contact import PublicContact

        return PublicContact(
            registry_id=contact_id,
            contact_type=contact_type,
            email=contact_data.email or "",
            voice=contact_data.voice or "",
            fax=contact_data.fax or "",
            name=(postal_info.name or "") if postal_info else "",
            org=(postal_info.org or "") if postal_info else "",
            city=(addr.city or "") if addr else "",
            pc=(addr.pc or "") if addr else "",
            cc=(addr.cc or "") if addr else "",
            sp=(addr.sp or "") if addr else "",
            **streets,
        )

    def _convert_ips(self, ip_list: List[str]) -> List:
        """Convert Ips to a list of epp.Ip objects
        use when sending update host command.
        if there are no ips an empty list will be returned

        Args:
            ip_list (list[str]): the new list of ips, may be empty
        Returns:
            edited_ip_list (list[epp.Ip]): list of epp.ip objects ready to
            be sent to the registry
        """
        import ipaddress

        epp_ips = []
        for ip_str in ip_list:
            ip_addr = ipaddress.ip_address(ip_str)
            epp_ips.append(epp.Ip(addr=ip_str, ip="v6" if ip_addr.version == 6 else None))
        return epp_ips

    def is_dns_needed(self):
        """Unused but kept in the codebase
        as this call should be made, but adds
        a lot of processing time
        when EPP calling is made more efficient
        this should be added back in

        The goal is to double check that
        the nameservers we set are in fact
        on the registry
        """
        self._invalidate_cache()
        nameserverList = self.nameservers
        return len(nameserverList) < 2

    def dns_not_needed(self):
        return not self.is_dns_needed()
