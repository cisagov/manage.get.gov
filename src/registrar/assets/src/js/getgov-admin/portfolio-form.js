import { hideElement, showElement } from './helpers-admin.js';

/**
 * A function for dynamically changing some fields on the portfolio admin model
 * IMPORTANT NOTE: The logic in this function is paired handlePortfolioSelection and should be refactored once we solidify our requirements.
*/
function handlePortfolioFields(){

    let isPageLoading = true
    let seniorOfficialContactList = document.querySelector(".field-senior_official .dja-address-contact-list");
    const federalAgency = document.querySelector(".field-federal_agency");
    // $ symbolically denotes that this is using jQuery
    let $federalAgency = django.jQuery("#id_federal_agency");
    let organizationType = document.getElementById("id_organization_type");
    let readonlyOrganizationType = document.querySelector(".field-organization_type .readonly");
    let organizationName = document.querySelector(".field-organization_name");
    let federalType = document.querySelector(".field-federal_type");
    let urbanization = document.querySelector(".field-urbanization");
    let stateTerritory = document.getElementById("id_state_territory");
    let $seniorOfficial = django.jQuery("#id_senior_official");
    let readonlySeniorOfficial = document.querySelector(".field-senior_official .readonly");

    function getFederalTypeFromAgency(agency) {
        let federalPortfolioApi = document.getElementById("federal_and_portfolio_types_from_agency_json_url").value;
        return fetch(`${federalPortfolioApi}?&agency_name=${agency}`)
            .then(response => {
                const statusCode = response.status;
                return response.json().then(data => ({ statusCode, data }));
            })
            .then(({ statusCode, data }) => {
                if (data.error) {
                    console.error("Error in AJAX call: " + data.error);
                    return;
                }
                return data.federal_type
            })
            .catch(error => {
                console.error("Error fetching federal and portfolio types: ", error);
                return null
            });
    }

    function getSeniorOfficialFromAgency(agency, seniorOfficialAddUrl) {
        let seniorOfficialApi = document.getElementById("senior_official_from_agency_json_url").value;
        return fetch(`${seniorOfficialApi}?agency_name=${agency}`)
            .then(response => {
                const statusCode = response.status;
                return response.json().then(data => ({ statusCode, data }));
            })
            .then(({ statusCode, data }) => {
                if (data.error) {
                    if (statusCode === 404) {

                        if ($seniorOfficial && $seniorOfficial.length > 0) {
                            $seniorOfficial.val("").trigger("change");
                        } else {
                            // Show the "create one now" text if this field is none in readonly mode.
                            readonlySeniorOfficial.innerHTML = `<a href="${seniorOfficialAddUrl}">No senior official found. Create one now.</a>`;
                        }

                        console.warn("Record not found: " + data.error);
                    } else {
                        console.error("Error in AJAX call: " + data.error);
                    }
                    return null;
                } else {
                    return data;
                }
            })
            .catch(error => {
                console.error("Error fetching senior official: ", error)
                return null;
            });
    }
    
    function handleOrganizationTypeChange(organizationType, organizationNameContainer, federalType) {
        if (organizationType && organizationNameContainer) {
            let selectedValue = organizationType.value;
            if (selectedValue === "federal") {
                hideElement(organizationNameContainer);
                showElement(federalAgency);
                if (federalType) {
                    showElement(federalType);
                }
            } else {
                showElement(organizationNameContainer);
                hideElement(federalAgency);
                if (federalType) {
                    hideElement(federalType);
                }
            }
        }
    }

    function handleFederalAgencyChange(federalAgency, organizationType, readonlyOrganizationType, organizationNameContainer, federalType) {
        if (!isPageLoading) {

            let selectedFederalAgency = federalAgency.find("option:selected").text();
            // There isn't a federal senior official associated with null records
            if (!selectedFederalAgency) {
                return;
            }

            let organizationTypeValue = organizationType ? organizationType.value : readonlyOrganizationType.innerText.toLowerCase();
            if (selectedFederalAgency !== "Non-Federal Agency") {
                if (organizationTypeValue !== "federal") {
                    if (organizationType){
                        organizationType.value = "federal";
                    }else {
                        readonlyOrganizationType.innerText = "Federal"
                    }
                }
            } else {
                if (organizationTypeValue === "federal") {
                    if (organizationType){
                        organizationType.value =  "";
                    }else {
                        readonlyOrganizationType.innerText =  "-"
                    }
                }
            }

            handleOrganizationTypeChange(organizationType, organizationNameContainer, federalType);

            // Determine if any changes are necessary to the display of portfolio type or federal type
            // based on changes to the Federal Agency
            getFederalTypeFromAgency(selectedFederalAgency).then((federalType) => updateReadOnly(federalType, '.field-federal_type'));
            
            hideElement(seniorOfficialContactList.parentElement);
            let seniorOfficialAddUrl = document.getElementById("senior-official-add-url").value;
            getSeniorOfficialFromAgency(selectedFederalAgency, seniorOfficialAddUrl).then((data) => {
                // Update the "contact details" blurb beneath senior official
                updateContactInfo(data);
                showElement(seniorOfficialContactList.parentElement);
                // Get the associated senior official with this federal agency
                let seniorOfficialId = data.id;
                let seniorOfficialName = [data.first_name, data.last_name].join(" ");
                if ($seniorOfficial && $seniorOfficial.length > 0) {
                    // If the senior official is a dropdown field, edit that
                    updateSeniorOfficialDropdown($seniorOfficial, seniorOfficialId, seniorOfficialName);
                }else {
                    if (readonlySeniorOfficial) {
                        let seniorOfficialLink = `<a href=/admin/registrar/seniorofficial/${seniorOfficialId}/change/>${seniorOfficialName}</a>`
                        readonlySeniorOfficial.innerHTML = seniorOfficialName ? seniorOfficialLink : "-";
                    }
                }
            });
            
        } else {
            isPageLoading = false;
        }

    }

    function updateSeniorOfficialDropdown(dropdown, seniorOfficialId, seniorOfficialName) {
        if (!seniorOfficialId || !seniorOfficialName || !seniorOfficialName.trim()){
            // Clear the field if the SO doesn't exist
            dropdown.val("").trigger("change");
            return;
        }
        // Add the senior official to the dropdown.
        // This format supports select2 - if we decide to convert this field in the future.
        if (dropdown.find(`option[value='${seniorOfficialId}']`).length) {
            // Select the value that is associated with the current Senior Official.
            dropdown.val(seniorOfficialId).trigger("change");
        } else { 
            // Create a DOM Option that matches the desired Senior Official. Then append it and select it.
            let userOption = new Option(seniorOfficialName, seniorOfficialId, true, true);
            dropdown.append(userOption).trigger("change");
        }
    }

    function handleStateTerritoryChange(stateTerritory, urbanizationField) {
        let selectedValue = stateTerritory.value;
        if (selectedValue === "PR") {
            showElement(urbanizationField)
        } else {
            hideElement(urbanizationField)
        }
    }

    /**
     * Utility that selects a div from the DOM using selectorString,
     * and updates a div within that div which has class of 'readonly'
     * so that the text of the div is updated to updateText
     * @param {*} updateText 
     * @param {*} selectorString 
     */
    function updateReadOnly(updateText, selectorString) {
        // find the div by selectorString
        const selectedDiv = document.querySelector(selectorString);
        if (selectedDiv) {
            // find the nested div with class 'readonly' inside the selectorString div
            const readonlyDiv = selectedDiv.querySelector('.readonly');
            if (readonlyDiv) {
                // Update the text content of the readonly div
                readonlyDiv.textContent = updateText !== null ? updateText : '-';
            }
        }
    }

    function updateContactInfo(data) {
        if (!seniorOfficialContactList) return;
    
        const titleSpan = seniorOfficialContactList.querySelector(".contact_info_title");
        const emailSpan = seniorOfficialContactList.querySelector(".contact_info_email");
        const phoneSpan = seniorOfficialContactList.querySelector(".contact_info_phone");
    
        if (titleSpan) { 
            titleSpan.textContent = data.title || "None";
        };

        // Update the email field and the content for the clipboard
        if (emailSpan) {
            let copyButton = seniorOfficialContactList.querySelector(".admin-icon-group");
            emailSpan.textContent = data.email || "None";
            if (data.email) {
                const clipboardInput = seniorOfficialContactList.querySelector(".admin-icon-group input");
                if (clipboardInput) {
                    clipboardInput.value = data.email;
                };
                showElement(copyButton);
            }else {
                hideElement(copyButton);
            }
        }

        if (phoneSpan) {
            phoneSpan.textContent = data.phone || "None";
        };
    }

    function initializePortfolioSettings() {
        if (urbanization && stateTerritory) {
            handleStateTerritoryChange(stateTerritory, urbanization);
        }
        handleOrganizationTypeChange(organizationType, organizationName, federalType);
    }

    function setEventListeners() {
        if ($federalAgency && (organizationType || readonlyOrganizationType)) {
            $federalAgency.on("change", function() {
                handleFederalAgencyChange($federalAgency, organizationType, readonlyOrganizationType, organizationName, federalType);
            });
        }
        if (urbanization && stateTerritory) {
            stateTerritory.addEventListener("change", function() {
                handleStateTerritoryChange(stateTerritory, urbanization);
            });
        }
        organizationType.addEventListener("change", function() {
            handleOrganizationTypeChange(organizationType, organizationName, federalType);
        });
    }

    // Run initial setup functions
    initializePortfolioSettings();
    setEventListeners();
}

export function initPortfolioFields() {
    document.addEventListener('DOMContentLoaded', function() {
        let isPortfolioPage = document.getElementById("portfolio_form");
        if (isPortfolioPage) {
            handlePortfolioFields();
        }
    });
}
