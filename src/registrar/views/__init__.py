from .domain_request import *
from .domain import (
    DomainView,
    DomainSeniorOfficialView,
    DomainOrgNameAddressView,
    DomainSubOrganizationView,
    DomainDNSView,
    DomainNameserversView,
    DomainDNSSECView,
    DomainDsDataView,
    DomainSecurityEmailView,
    DomainUsersView,
    DomainAddUserView,
    DomainInvitationCancelView,
    DomainDeleteUserView,
    DomainDNSRecordsView,
    DomainRenewalView,
    DomainDeleteView,
    DomainLifecycleView,
)
from .user_profile import UserProfileView, FinishProfileSetupView
from .health import *
from .version_info import *
from .index import *
from .portfolios import *
from .transfer_user import TransferUserView
from .member_domains_json import PortfolioMemberDomainsJson
from .portfolio_members_json import PortfolioMembersJson
# TODO - this is on dev only, 
# option 1: change it so this view is only added  if settings indicates local dev
# option 2: keep as is, but update to be a class (function was lazy)
from .dev_auto_login import dev_auto_login 
