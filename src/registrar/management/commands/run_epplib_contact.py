from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from xml.dom.minidom import parseString
import logging
from types import SimpleNamespace

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

        # Build an UpdateContact using epplib models so we can
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

        # Build a raw UpdateContact request that contains a
        # nested <disclose><addr><street/></addr></disclose> element so we
        # can test the registry's per-street disclose acceptance without
        # modifying epplib itself.
        if options.get("disclose_street_xml"):
            try:
                # Build an epplib UpdateContact as a base so we replicate the
                # exact namespace declarations/schemaLocation that epplib
                # produces, then inject a nested <disclose><addr><street/></addr></disclose>
                # element into the <chg> element. 
                from lxml import etree as LET
                from lxml.etree import QName as LQName
                from epplib.constants import NAMESPACE as EPPNS
                from epplib.models import PostalInfo, ContactAddr

                sample_addr = ContactAddr(
                    street=["1234 main st", "#10"],
                    city="somewhereelse",
                    sp="OH",
                    pc="33774",
                    cc="US",
                )
                sample_postal = PostalInfo(
                    name="Other Test Name",
                    org="Other Test Org",
                    addr=sample_addr,
                    type="loc",
                )

                base_cmd = commands.UpdateContact(
                    id=registry_id,
                    postal_info=sample_postal,
                )

                base_raw = base_cmd.xml()
                root = LET.fromstring(base_raw)

                chg = root.find('.//{*}chg')
                if chg is None:
                    raise RuntimeError("Couldn't find chg element in base XML")

                disclose_el = LET.Element(LQName(EPPNS.NIC_CONTACT, "disclose"), flag="0")
                addr_el = LET.SubElement(disclose_el, LQName(EPPNS.NIC_CONTACT, "addr"))
                LET.SubElement(addr_el, LQName(EPPNS.NIC_CONTACT, "street"))

                addr_el.set("type", "loc")

                chg.append(disclose_el)

                xml_bytes = LET.tostring(root, encoding="utf-8", xml_declaration=True)


                cmd = SimpleNamespace(
                    xml=lambda *a, **kw: xml_bytes,
                    response_class=getattr(base_cmd, "response_class", None),
                )
            except Exception as e:
                logger.exception("Failed to build raw disclose-street XML: %s", e)
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

        # print response
        try:
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
