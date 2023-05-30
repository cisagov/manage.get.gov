# How to change the default contact data

The defaults are located in [src/registrar/models/public_contact.py](../../src/registrar/models/public_contact.py). Change them in the source code and re-deploy.

The choice of which fields to disclose is hardcoded in [src/registrar/models/domain.py](../../src/registrar/models/domain.py) (May 23) but in the future this may become customizable by registrants.