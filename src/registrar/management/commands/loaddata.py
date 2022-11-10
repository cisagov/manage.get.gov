from django.core.management.commands import loaddata
from auditlog.context import disable_auditlog  # type: ignore


class Command(loaddata.Command):
    def handle(self, *args, **options):
        # django-auditlog has some bugs with fixtures
        # https://github.com/jazzband/django-auditlog/issues/17
        with disable_auditlog():
            super(Command, self).handle(*args, **options)
