import { hookupYesNoListener } from './radios.js';
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
import { initPortfolioNewMemberPageToggle, initAddNewMemberPageListeners, initPortfolioMemberPageRadio } from './portfolio-member-page.js';
import { initDomainRequestForm } from './domain-request-form.js';
import { initDomainManagersPage } from './domain-managers.js';
import { initDomainDNSSEC } from './domain-dnssec.js';
import { initFormErrorHandling } from './form-errors.js';
import { initButtonLinks } from '../getgov-admin/button-utils.js';

initDomainValidators();

initFormsetsForms();
initFormNameservers();
initFormDSData();

hookupYesNoListener("other_contacts-has_other_contacts",'other-employees', 'no-other-employees');
hookupYesNoListener("additional_details-has_anything_else_text",'anything-else', null);
hookupYesNoListener("additional_details-has_cisa_representative",'cisa-representative', null);
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

// Init the portfolio new member page
initPortfolioMemberPageRadio();
initPortfolioNewMemberPageToggle();
initAddNewMemberPageListeners();

initButtonLinks();
