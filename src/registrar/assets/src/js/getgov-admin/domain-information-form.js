import { handleSuborganizationFields } from './helpers-portfolio-dynamic-fields.js';

/**
 * A function for dynamic DomainInformation fields
*/
export function initDynamicDomainInformationFields(){
    const domainInformationPage = document.getElementById("domaininformation_form");
    if (domainInformationPage) {
        handleSuborganizationFields();
    }

    // DomainInformation is embedded inside domain so this should fire there too
    const domainPage = document.getElementById("domain_form");
    if (domainPage) {
        handleSuborganizationFields(portfolioDropdownSelector="#id_domain_info-0-portfolio", suborgDropdownSelector="#id_domain_info-0-sub_organization");
    }
}
