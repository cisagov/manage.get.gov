import { handlePortfolioSelection } from './helpers-portfolio-dynamic-fields.js';

/**
 * A function for dynamic DomainRequest fields
*/
export function initDynamicDomainInformationFields(){
    const domainInformationPage = document.getElementById("domaininformation_form");
    if (domainInformationPage) {
        handlePortfolioSelection();
    }
}
