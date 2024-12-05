import { hookupYesNoListener, hookupRadioTogglerListener } from './radios.js';
import { initDomainValidators } from './domain-validators.js';
import { initFormsetsForms, triggerModalOnDsDataForm, nameserversFormListener } from './formset-forms.js';
import { initializeUrbanizationToggle } from './urbanization.js';
import { userProfileListener, finishUserSetupListener } from './user-profile.js';
import { loadInitialValuesForComboBoxes } from './combobox.js';
import { handleRequestingEntityFieldset } from './requesting-entity.js';
import { initDomainsTable } from './table-domains.js';
import { initDomainRequestsTable } from './table-domain-requests.js';
import { initMembersTable } from './table-members.js';
import { initMemberDomainsTable } from './table-member-domains.js';
import { initEditMemberDomainsTable } from './table-edit-member-domains.js';
import { initPortfolioMemberPageToggle } from './portfolio-member-page.js';
import { initAddNewMemberPageListeners } from './portfolio-member-page.js';

initDomainValidators();

initFormsetsForms();
triggerModalOnDsDataForm();
nameserversFormListener();

hookupYesNoListener("other_contacts-has_other_contacts",'other-employees', 'no-other-employees');
hookupYesNoListener("additional_details-has_anything_else_text",'anything-else', null);
hookupRadioTogglerListener(
  'member_access_level', 
  {
    'admin': 'new-member-admin-permissions',
    'basic': 'new-member-basic-permissions'
  }
);
hookupYesNoListener("additional_details-has_cisa_representative",'cisa-representative', null);
initializeUrbanizationToggle();

userProfileListener();
finishUserSetupListener();

loadInitialValuesForComboBoxes();

handleRequestingEntityFieldset();

initDomainsTable();
initDomainRequestsTable();
initMembersTable();
initMemberDomainsTable();
initEditMemberDomainsTable();

initPortfolioMemberPageToggle();
initAddNewMemberPageListeners();
