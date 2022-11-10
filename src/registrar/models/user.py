from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    A custom user model that performs identically to the default user model
    but can be customized later.
    """

    def __str__(self):
        # this info is pulled from Login.gov
        if self.first_name or self.last_name:
            return f"{self.first_name or ''} {self.last_name or ''}"
        elif self.email:
            return self.email
        else:
            return self.username
