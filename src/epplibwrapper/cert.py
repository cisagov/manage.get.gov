import os
import tempfile

from django.conf import settings


class Cert:
    """
    Location of client certificate as written to disk.

    This is needed because the certificate is stored as an environment
    variable but Python's ssl library requires a file.
    """

    def __init__(self, data=settings.SECRET_REGISTRY_CERT) -> None:
        self.filename = self._write(data)

    def __del__(self):
        """Remove the files when this object is garbage collected."""
        os.unlink(self.filename)

    def _write(self, data) -> str:
        """Write data to a secure tempfile. Returns the path."""
        _, path = tempfile.mkstemp()
        with open(path, "wb") as file:
            file.write(data)
        return path


class Key(Cert):
    """Location of private key as written to disk."""

    def __init__(self) -> None:
        super().__init__(data=settings.SECRET_REGISTRY_KEY)
