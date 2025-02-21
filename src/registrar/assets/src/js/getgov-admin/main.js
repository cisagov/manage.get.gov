import { initModals } from './modals.js';
import { initCopyToClipboard } from './copy-to-clipboard.js';
import { initFilterHorizontalWidget } from './filter-horizontal.js';
import { initDescriptions } from './show-more-description.js';
import { initSubmitBar } from './submit-bar.js';
import { 
    initIneligibleModal, 
    initAssignToMe,  
    initActionNeededEmail, 
    initRejectedEmail, 
    initApprovedDomain, 
    initCopyRequestSummary,
    initDynamicDomainRequestFields } from './domain-request-form.js';
import { initDomainFormTargetBlankButtons } from './domain-form.js';
import { initDynamicPortfolioFields } from './portfolio-form.js';
import { initDynamicDomainInformationFields } from './domain-information-form.js';
import { initDynamicDomainFields } from './domain-form.js';
import { initAnalyticsDashboard } from './analytics.js';
import { initButtonLinks } from './button-utils.js';

// General
initModals();
initCopyToClipboard();
initFilterHorizontalWidget();
initDescriptions();
initSubmitBar();
initButtonLinks();

// Domain request
initIneligibleModal();
initAssignToMe();
initActionNeededEmail();
initRejectedEmail();
initApprovedDomain();
initCopyRequestSummary();
initDynamicDomainRequestFields();

// Domain
initDomainFormTargetBlankButtons();
initDynamicDomainFields();

// Portfolio
initDynamicPortfolioFields();

// Domain information
initDynamicDomainInformationFields();

// Analytics dashboard
initAnalyticsDashboard();
