from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from xml.dom.minidom import parseString
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

    def handle(self, *args, **options):
        registry_id = options.get("registry_id")
        do_send = options.get("send", False)

        try:
            # Import here so Django settings are already configured
            from epplibwrapper import commands, CLIENT
            # cert/key objects are provided by the client module
            from epplibwrapper import client as epplib_client_module
        except Exception as e:
            logger.exception(
                "Failed to import epplibwrapper: %s", e
            )
            raise CommandError(
                "Could not import epplibwrapper; ensure dependencies are "
                "installed and settings are correct."
            )

    # Verify settings and cert/key, and attempt to initialize a
    # client to validate access.
        if options.get("check"):
            from django.conf import settings
            import os

            missing = []
            for name in (
                "SECRET_REGISTRY_CL_ID",
                "SECRET_REGISTRY_PASSWORD",
                "SECRET_REGISTRY_HOSTNAME",
                "SECRET_REGISTRY_KEY_PASSPHRASE",
            ):
                if not getattr(settings, name, None):
                    missing.append(name)

            if missing:
                self.stderr.write(
                    "Missing registry settings: {}. Check failed.".format(
                        ", ".join(missing)
                    )
                )
                raise CommandError(
                    "Check failed due to missing settings."
                )

            cert_obj = getattr(epplib_client_module, "CERT", None)
            key_obj = getattr(epplib_client_module, "KEY", None)
            if not cert_obj or not key_obj:
                self.stderr.write(
                    "Certificate or key objects not available. "
                    "Ensure certs are provisioned."
                )
                raise CommandError(
                    "Check failed: missing certificate/key."
                )

            cert_file = getattr(cert_obj, "filename", None)
            key_file = getattr(key_obj, "filename", None)
            if not cert_file or not key_file:
                self.stderr.write(
                    "Certificate or key file paths not set on Cert/Key "
                    "objects."
                )
                raise CommandError(
                    "Check failed: cert/key paths missing."
                )

            if not os.path.exists(cert_file) or not os.path.exists(key_file):
                self.stderr.write(
                    "Cert/key files not found: {}, {}".format(
                        cert_file, key_file
                    )
                )
                raise CommandError(
                    "Check failed: cert/key files missing."
                )

            if (
                not os.access(cert_file, os.R_OK)
                or not os.access(key_file, os.R_OK)
            ):
                self.stderr.write(
                    "Cert/key files are not readable by this user."
                )
                raise CommandError(
                    "Check failed: cert/key unreadable."
                )

            # Attempt to initialize the client and login. This performs a
            # real network login; it's intended for sandbox environments.
            try:
                self.stdout.write(
                    "Attempting to initialize registry client (login)..."
                )
                # call the wrapper's init helper to force initialization
                CLIENT._initialize_client()
                self.stdout.write("Check: login successful.")
                # close connection after successful login
                try:
                    CLIENT._disconnect()
                except Exception:
                    # best-effort close
                    pass
            except Exception as e:
                logger.exception("Client init failed: %s", e)
                raise CommandError(
                    f"Check failed: {e}"
                )

        # build registry command
        try:
            cmd = commands.InfoContact(id=registry_id)
        except Exception as e:
            logger.exception("Failed to construct InfoContact command: %s", e)
            raise CommandError(f"Failed to construct InfoContact command: {e}")

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
            resp = CLIENT.send(cmd, cleaned=True)
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
                    try:
                        for item in res_data:
                            xml_fn = getattr(item, "xml", None)
                            if callable(xml_fn):
                                self.stdout.write(pretty_xml(xml_fn()))
                            else:
                                self.stdout.write(repr(item))
                    except Exception:
                        self.stdout.write(repr(res_data))
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
