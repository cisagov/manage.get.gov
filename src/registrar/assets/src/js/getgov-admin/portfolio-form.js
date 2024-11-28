import { hideElement, showElement } from './helpers-admin.js';

/**
 * A function for dynamically changing some fields on the portfolio admin model
 * IMPORTANT NOTE: The logic in this function is paired handlePortfolioSelection and should be refactored once we solidify our requirements.
*/
export function initDynamicPortfolioFields(){

    // the federal agency change listener fires on page load, which we don't want.
    var isInitialPageLoad = true

    // This is the additional information that exists beneath the SO element.
    var contactList = document.querySelector(".field-senior_official .dja-address-contact-list");
    const federalAgencyContainer = document.querySelector(".field-federal_agency");
    document.addEventListener('DOMContentLoaded', function() {

        let isPortfolioPage = document.getElementById("portfolio_form");
        if (!isPortfolioPage) {
            return;
        }

        // $ symbolically denotes that this is using jQuery
        let $federalAgency = django.jQuery("#id_federal_agency");
        let organizationType = document.getElementById("id_organization_type");
        let readonlyOrganizationType = document.querySelector(".field-organization_type .readonly");

        let organizationNameContainer = document.querySelector(".field-organization_name");
        let federalType = document.querySelector(".field-federal_type");

        if ($federalAgency && (organizationType || readonlyOrganizationType)) {
            // Attach the change event listener
            $federalAgency.on("change", function() {
                handleFederalAgencyChange($federalAgency, organizationType, readonlyOrganizationType, organizationNameContainer, federalType);
            });
        }
        
        // Handle dynamically hiding the urbanization field
        let urbanizationField = document.querySelector(".field-urbanization");
        let stateTerritory = document.getElementById("id_state_territory");
        if (urbanizationField && stateTerritory) {
            // Execute this function once on load
            handleStateTerritoryChange(stateTerritory, urbanizationField);

            // Attach the change event listener for state/territory
            stateTerritory.addEventListener("change", function() {
                handleStateTerritoryChange(stateTerritory, urbanizationField);
            });
        }

        // Handle hiding the organization name field when the organization_type is federal.
        // Run this first one page load, then secondly on a change event.
        handleOrganizationTypeChange(organizationType, organizationNameContainer, federalType);
        organizationType.addEventListener("change", function() {
            handleOrganizationTypeChange(organizationType, organizationNameContainer, federalType);
        });
    });

    function handleOrganizationTypeChange(organizationType, organizationNameContainer, federalType) {
        if (organizationType && organizationNameContainer) {
            let selectedValue = organizationType.value;
            if (selectedValue === "federal") {
                hideElement(organizationNameContainer);
                showElement(federalAgencyContainer);
                if (federalType) {
                    showElement(federalType);
                }
            } else {
                showElement(organizationNameContainer);
                hideElement(federalAgencyContainer);
                if (federalType) {
                    hideElement(federalType);
                }
            }
        }
    }

    function handleFederalAgencyChange(federalAgency, organizationType, readonlyOrganizationType, organizationNameContainer, federalType) {
        // Don't do anything on page load
        if (isInitialPageLoad) {
            isInitialPageLoad = false;
            return;
        }

        // Set the org type to federal if an agency is selected
        let selectedText = federalAgency.find("option:selected").text();

        // There isn't a federal senior official associated with null records
        if (!selectedText) {
            return;
        }

        let organizationTypeValue = organizationType ? organizationType.value : readonlyOrganizationType.innerText.toLowerCase();
        if (selectedText !== "Non-Federal Agency") {
            if (organizationTypeValue !== "federal") {
                if (organizationType){
                    organizationType.value = "federal";
                }else {
                    readonlyOrganizationType.innerText = "Federal"
                }
            }
        }else {
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
        let federalPortfolioApi = document.getElementById("federal_and_portfolio_types_from_agency_json_url").value;
        fetch(`${federalPortfolioApi}?&agency_name=${selectedText}`)
        .then(response => {
            const statusCode = response.status;
            return response.json().then(data => ({ statusCode, data }));
        })
        .then(({ statusCode, data }) => {
            if (data.error) {
                console.error("Error in AJAX call: " + data.error);
                return;
            }
            updateReadOnly(data.federal_type, '.field-federal_type');
        })
        .catch(error => console.error("Error fetching federal and portfolio types: ", error));

        // Hide the contactList initially. 
        // If we can update the contact information, it'll be shown again.
        hideElement(contactList.parentElement);
        
        let seniorOfficialAddUrl = document.getElementById("senior-official-add-url").value;
        let $seniorOfficial = django.jQuery("#id_senior_official");
        let readonlySeniorOfficial = document.querySelector(".field-senior_official .readonly");
        let seniorOfficialApi = document.getElementById("senior_official_from_agency_json_url").value;
        fetch(`${seniorOfficialApi}?agency_name=${selectedText}`)
        .then(response => {
            const statusCode = response.status;
            return response.json().then(data => ({ statusCode, data }));
        })
        .then(({ statusCode, data }) => {
            if (data.error) {
                // Clear the field if the SO doesn't exist.
                if (statusCode === 404) {
                    if ($seniorOfficial && $seniorOfficial.length > 0) {
                        $seniorOfficial.val("").trigger("change");
                    }else {
                        // Show the "create one now" text if this field is none in readonly mode.
                        readonlySeniorOfficial.innerHTML = `<a href="${seniorOfficialAddUrl}">No senior official found. Create one now.</a>`;
                    }
                    console.warn("Record not found: " + data.error);
                }else {
                    console.error("Error in AJAX call: " + data.error);
                }
                return;
            }

            // Update the "contact details" blurb beneath senior official
            updateContactInfo(data);
            showElement(contactList.parentElement);
            
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
        })
        .catch(error => console.error("Error fetching senior official: ", error));

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
        if (!contactList) return;
    
        const titleSpan = contactList.querySelector(".contact_info_title");
        const emailSpan = contactList.querySelector(".contact_info_email");
        const phoneSpan = contactList.querySelector(".contact_info_phone");
    
        if (titleSpan) { 
            titleSpan.textContent = data.title || "None";
        };

        // Update the email field and the content for the clipboard
        if (emailSpan) {
            let copyButton = contactList.querySelector(".admin-icon-group");
            emailSpan.textContent = data.email || "None";
            if (data.email) {
                const clipboardInput = contactList.querySelector(".admin-icon-group input");
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
}
