import { hookupYesNoListener, hookupCallbacksToRadioToggler } from './radios.js';
import { initDomainValidators } from './domain-validators.js';
import { initFormsetsForms } from './formset-forms.js';
import { initFormNameservers } from './form-nameservers';
import { initFormDSData } from './form-dsdata.js';
import { initializeUrbanizationToggle } from './urbanization.js';
import { userProfileListener, finishUserSetupListener } from './user-profile.js';
import { handleRequestingEntityFieldset } from './requesting-entity.js';
import { initDomainsTable } from './table-domains.js';
import { initDomainRequestsTable } from './table-domain-requests.js';
import { initMembersTable } from './table-members.js';
import { initMemberDomainsTable } from './table-member-domains.js';
import { initEditMemberDomainsTable } from './table-edit-member-domains.js';
import { initPortfolioNewMemberPageToggle, initAddNewMemberPageListeners, initPortfolioMemberPage } from './portfolio-member-page.js';
import { initDomainRequestForm } from './domain-request-form.js';
import { initDomainManagersPage } from './domain-managers.js';
import { initDomainDNSSEC } from './domain-dnssec.js';
import { initFormErrorHandling } from './form-errors.js';
import { domain_purpose_choice_callbacks } from './domain-purpose-form.js';
import { initButtonLinks } from '../getgov-admin/button-utils.js';
import { initOrganizationsNavDropdown } from './organizations-dropdown.js';
import { domainDeletionEventListener } from './domain-deletion-form.js';
import { initDynamicDNSRecordFormFields } from './domain-dns-record-content.js';

initDomainValidators();

initFormsetsForms();
initFormNameservers();
initFormDSData();

hookupYesNoListener("other_contacts-has_other_contacts",'other-employees', 'no-other-employees');
hookupYesNoListener("additional_details-has_anything_else_text",'anything-else', null);
hookupYesNoListener("additional_details-has_cisa_representative",'cisa-representative', null);
hookupYesNoListener("portfolio_additional_details-has_anything_else_text", 'anything-else-details-container', null);
hookupYesNoListener("dotgov_domain-feb_naming_requirements", null, "domain-naming-requirements-details-container");

hookupCallbacksToRadioToggler("purpose-feb_purpose_choice", domain_purpose_choice_callbacks);

hookupYesNoListener("purpose-has_timeframe", "purpose-timeframe-details-container", null);
hookupYesNoListener("purpose-is_interagency_initiative", "purpose-interagency-initaitive-details-container", null);

initializeUrbanizationToggle();

userProfileListener();
finishUserSetupListener();

handleRequestingEntityFieldset();

initDomainsTable();
initDomainRequestsTable();
initMembersTable();
initMemberDomainsTable();
initEditMemberDomainsTable();

initDomainRequestForm();
initDomainManagersPage();
initDomainDNSSEC();

initFormErrorHandling();

// Init the portfolio member page
initPortfolioMemberPage();

// Init the portfolio new member page
initPortfolioNewMemberPageToggle();
initAddNewMemberPageListeners();

initButtonLinks();
domainDeletionEventListener();

// Init the portfolios nav dropdown
initOrganizationsNavDropdown();

// Init the dynamic DNS content labels and ensure HTMX re-runs after POST
initDynamicDNSRecordFormFields();

document.addEventListener('htmx:afterSettle', (evt) => {
    initDynamicDNSRecordFormFields();
});