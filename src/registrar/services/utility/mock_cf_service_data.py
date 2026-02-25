from registrar.services.cloudflare_service import CloudflareService

CF_ACCOUNTS = [
    {
        "account_tag": "234asdf",
        "account_pubname": "Account for hello.gov",
        "account_type": "standard",
        "created_on": "2025-10-08T21:07:18.651092Z",
        "settings": {
            "enforce_two_factor": False,
            "api_access_enabled": False,
            "access_approval_expiry": None,
            "use_account_custom_ns_by_default": False,
        },
    },
    {
        "account_tag": "786541939c054442b78dcddf714e45d9",
        "account_pubname": "Fake account name",
        "account_type": "enterprise",
        "created_on": "2025-10-08T21:21:38.401706Z",
        "settings": {
            "enforce_two_factor": False,
            "api_access_enabled": False,
            "access_approval_expiry": None,
            "use_account_custom_ns_by_default": False,
        },
    },
    {
        "account_tag": "a1234",
        "account_pubname": "Account for exists.gov",
        "account_type": "enterprise",
        "created_on": "2025-10-08T21:21:38.401706Z",
        "settings": {
            "enforce_two_factor": False,
            "api_access_enabled": False,
            "access_approval_expiry": None,
            "use_account_custom_ns_by_default": False,
        },
    },
]

CF_ACCOUNTS_RESULT_INFO = {"count": 3, "page": 1, "per_page": 20, "total_count": 0}

CF_ACCOUNT_ZONES = [
    {  # This record referenced for existing account with existing zone
        "id": "z54321",
        "account": {"id": "a1234", "name": "Account for exists.gov"},
        "created_on": "2014-01-01T05:20:00.12345Z",
        "modified_on": "2014-01-01T05:20:00.12345Z",
        "name": "exists.gov",
        "name_servers": [
            "rainbow.dns.gov",
            "rainbow2.dns.gov",
        ],
        "vanity_name_servers": [],
        "status": "pending",
        "tenant": {"id": CloudflareService.tenant_id, "name": "Fake dotgov"},
    }
]

CF_ACCOUNT_ZONES_RESULT_INFO = {"count": 1, "page": 1, "per_page": 20, "total_count": 1, "total_pages": 1}
