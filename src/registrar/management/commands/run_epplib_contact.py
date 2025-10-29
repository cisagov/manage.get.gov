from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from xml.dom.minidom import parseString
import xml.etree.ElementTree as ET
from types import SimpleNamespace
import logging

logger = logging.getLogger(__name__)


def pretty_xml(s: str) -> str:
    try:
        return parseString(s).toprettyxml()
    except Exception:
        return s


class Command(BaseCommand):
    help = (
        "Build or send an EPP InfoContact command via "
        "epplibwrapper."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "registry_id",
            type=str,
            help="Registry contact id to query",
        )
        parser.add_argument(
            "--send",
            action="store_true",
            dest="send",
            help=(
                "Actually send command to registry "
            ),
        )
        parser.add_argument(
            "--check",
            action="store_true",
            dest="check",
            help=(
                "Check: verify settings/certs and attempt a login to the "
                "registry. Does not send an InfoContact unless --send is also "
                "provided."
            ),
        )
        parser.add_argument(
            "--update-via-manual-xml",
            action="store_true",
            dest="disclose_street_xml",
            help=(
                "Build (and optionally send with --send) an UpdateContact XML "
                "that uses a nested disclose/addr/street element to request "
                "hiding only the street element"
            ),
        )
        parser.add_argument(
            "--update-via-epplib",
            action="store_true",
            dest="update_via_epplib",
            help=(
                "Build (and optionally send with --send) an UpdateContact "
                "using the epplib model"
            ),
        )

    def handle(self, *args, **options):
        registry_id = options.get("registry_id")
        do_send = options.get("send", False)

        try:
            # Import here so Django settings are already configured
            from epplibwrapper import commands, CLIENT

        except Exception as e:
            logger.exception(
                "Failed to import epplibwrapper: %s", e
            )
            raise CommandError(
                "Could not import epplibwrapper; ensure dependencies are "
                "installed and settings are correct."
            )


        # build registry command
        try:
            cmd = commands.InfoContact(id=registry_id)
        except Exception as e:
            logger.exception("Failed to construct InfoContact command: %s", e)
            raise CommandError(f"Failed to construct InfoContact command: {e}")

        # Note: when building manual raw XML we wrap the string in a tiny
        # object exposing xml() below using SimpleNamespace so it behaves
        # like epplib command objects.

        # If requested, build an UpdateContact using epplib models so you can
        # compare its XML to the raw disclose-street XML. This will use the
        # library's DiscloseField (ADDR) which hides the entire address.
        if options.get("update_via_epplib"):
            try:
                from epplib.models import (
                    Disclose,
                    DiscloseField,
                    ContactAddr,
                    PostalInfo,
                )

                sample_addr = ContactAddr(
                    street=["123 main st", "#5"],
                    city="somewhere",
                    sp="FL",
                    pc="33547",
                    cc="US",
                )
                sample_postal = PostalInfo(
                    name="Test Name",
                    org="Test Org",
                    addr=sample_addr,
                    type="loc",
                )

                cmd = commands.UpdateContact(
                    id=registry_id,
                    disclose=Disclose(
                        flag=False,
                        fields={DiscloseField.ADDR},
                        types={DiscloseField.ADDR: "loc"},
                    ),
                    postal_info=sample_postal,
                )
            except Exception as e:
                logger.exception(
                    "Failed to construct epplib UpdateContact: %s", e
                )
                raise CommandError(
                    f"Failed to build UpdateContact via epplib: {e}"
                )

        # If requested, build a raw UpdateContact request that contains a
        # nested <disclose><addr><street/></addr></disclose> element so we
        # can test the registry's per-street disclose acceptance without
        # modifying epplib itself.
        if options.get("disclose_street_xml"):
            try:
                epp_ns = "urn:ietf:params:xml:ns:epp-1.0"
                contact_ns = "urn:ietf:params:xml:ns:contact-1.0"
                # register namespaces so output contains prefixes/declarations
                ET.register_namespace("", epp_ns)
                ET.register_namespace("contact", contact_ns)

                root = ET.Element(f"{{{epp_ns}}}epp")
                command_el = ET.SubElement(root, f"{{{epp_ns}}}command")
                update_el = ET.SubElement(command_el, f"{{{epp_ns}}}update")
                c_update = ET.SubElement(update_el, f"{{{contact_ns}}}update")
                c_id = ET.SubElement(c_update, f"{{{contact_ns}}}id")
                c_id.text = registry_id

                disclose = ET.SubElement(
                    c_update, f"{{{contact_ns}}}disclose", {"flag": "0"}
                )
                addr = ET.SubElement(disclose, f"{{{contact_ns}}}addr")
                ET.SubElement(addr, f"{{{contact_ns}}}street")

                c_chg = ET.SubElement(c_update, f"{{{contact_ns}}}chg")
                postal = ET.SubElement(c_chg, f"{{{contact_ns}}}postalInfo")
                name_el = ET.SubElement(postal, f"{{{contact_ns}}}name")
                name_el.text = "Test Name"
                org_el = ET.SubElement(postal, f"{{{contact_ns}}}org")
                org_el.text = "Test Org"
                addr_el = ET.SubElement(postal, f"{{{contact_ns}}}addr")
                ET.SubElement(
                    addr_el, f"{{{contact_ns}}}street"
                ).text = "123 main st"
                ET.SubElement(
                    addr_el, f"{{{contact_ns}}}street"
                ).text = "#5"
                ET.SubElement(
                    addr_el, f"{{{contact_ns}}}city"
                ).text = "somewhere"
                ET.SubElement(addr_el, f"{{{contact_ns}}}sp").text = "FL"
                ET.SubElement(
                    addr_el, f"{{{contact_ns}}}pc"
                ).text = "33547"
                ET.SubElement(addr_el, f"{{{contact_ns}}}cc").text = "US"

                xml_str = ET.tostring(root, encoding="unicode")

                # ensure the addr element carries the 'type' attribute the
                # registry expects (some registries require the attribute on
                # the <addr> element rather than on postalInfo)
                try:
                    root = ET.fromstring(xml_str)
                    for a in root.findall('.//{'+contact_ns+'}addr'):
                        a.set('type', 'loc')
                    xml_str = ET.tostring(root, encoding='unicode')
                except Exception:
                    pass

                # Wrap the raw XML string in a tiny object exposing xml()
                cmd = SimpleNamespace(xml=lambda: xml_str)
            except Exception as e:
                logger.exception(
                    "Failed to build raw disclose-street XML: %s", e
                )
                raise CommandError(f"Failed to build XML: {e}")

        # show request XML
        try:
            xml_req = cmd.xml()
            self.stdout.write("--- Request XML ---")
            self.stdout.write(pretty_xml(xml_req))
        except Exception:
            self.stdout.write(repr(cmd))

        if not do_send:
            self.stdout.write(
                "\nDry-run complete. Re-run with --send to actually "
                "contact the registry."
            )
            return

        # send via module-level CLIENT instance
        try:
            self.stdout.write("Sending command to registry...")
            send_cmd = cmd

            resp = CLIENT.send(send_cmd, cleaned=True)
        except Exception as e:
            logger.exception("Error while sending command: %s", e)
            raise CommandError(f"Error while sending command: {e}")

        # print response in a way consistent with other code/tests: epplib may
        # return a Result-like object (with code/msg/res_data), raw XML bytes,
        # or an object exposing xml().
        try:
            # Result-like object (parsed): has 'code' and possibly 'res_data'
            if hasattr(resp, "code"):
                self.stdout.write(
                    "Response code: {}".format(getattr(resp, "code", None))
                )
                self.stdout.write(
                    "Response message: {}".format(getattr(resp, "msg", None))
                )
                res_data = getattr(resp, "res_data", None)
                if res_data:
                    self.stdout.write("--- Response res_data ---")
                    for item in res_data:
                        xml_fn = getattr(item, "xml", None)
                        if callable(xml_fn):
                            self.stdout.write(pretty_xml(xml_fn()))
                        else:
                            self.stdout.write(repr(item))
                else:
                    self.stdout.write(repr(resp))
            elif isinstance(resp, (bytes, str)):
                raw = resp.decode() if isinstance(resp, bytes) else resp
                self.stdout.write("--- Response XML ---")
                self.stdout.write(pretty_xml(raw))
            else:
                xml_fn = getattr(resp, "xml", None)
                if callable(xml_fn):
                    raw_xml = xml_fn()
                    self.stdout.write("--- Response XML ---")
                    self.stdout.write(pretty_xml(raw_xml))
                else:
                    self.stdout.write("Response repr:")
                    self.stdout.write(repr(resp))
        except Exception as e:
            logger.exception("Failed to pretty-print response: %s", e)
            self.stdout.write(repr(resp))
