import { handlePortfolioSelection } from './helpers-portfolio-dynamic-fields.js';

/**
 * A function for dynamic DomainInformation fields
*/
export function initDynamicDomainInformationFields(){
    const domainInformationPage = document.getElementById("domaininformation_form");
    if (domainInformationPage) {
        console.log("handling domain information page");
        handlePortfolioSelection();
    }
}
