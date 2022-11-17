"""
This file defines a number of mock functions which can be used to simulate
communication with the registry until that integration is implemented.
"""
from datetime import datetime

def domain_check(_):
    """ Is domain available for registration? """
    return True

def domain_info(domain):
    """ What does the registry know about this domain? """
    return {
        "name": domain,
        "roid": "EXAMPLE1-REP",
        "status": ["ok"],
        "registrant": "jd1234",
        "contact": {
            "admin": "sh8013",
            "tech": None,
        },
        "ns": {
            f"ns1.{domain}",
            f"ns2.{domain}",
        },
        "host": [
            f"ns1.{domain}",
            f"ns2.{domain}",
        ],
        "sponsor": "ClientX",
        "creator": "ClientY",
        # TODO: think about timezones
        "creation_date": datetime.today(),
        "updator": "ClientX",
        "last_update_date": datetime.today(),
        "expiration_date": datetime.today(),
        "last_transfer_date": datetime.today(),
    }


