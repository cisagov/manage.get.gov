Django OpenID Connect (OIDC) authentication provider
====================================================

This module makes it easy to integrate OpenID Connect as an authentication source in a Django project.

Behind the scenes, it uses Roland Hedberg's great pyoidc library.

Modified by JHUAPL BOSS to support Python3

Modified by Thomas Frössman with fixes and additional modifications.

A note for anyone viewing this file from the .gov repository:

This code has been included from its upstream counterpart in order to minimize external dependencies. Here is an excerpt from setup.py::

    name='django-oidc-tf',
    description="""A Django OpenID Connect (OIDC) authentication backend""",
    author='Thomas Frössman',
    author_email='thomasf@jossystem.se',
    url='https://github.com/py-pa/django-oidc',
    packages=[
        'djangooidc',
    ],
    include_package_data=True,
    install_requires=[
        'django>=1.10',
        'oic>=0.10.0',
    ],

It was taken from https://github.com/koriaf/django-oidc at ae4a0ba5e6bfda1495f9447a507e6f54cc056980.
