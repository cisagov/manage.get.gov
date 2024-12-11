import { hideElement, showElement } from './helpers-admin.js';

/**
 * A function for dynamically changing some fields on the portfolio admin model
 * IMPORTANT NOTE: The logic in this function is paired handlePortfolioSelection and should be refactored once we solidify our requirements.
*/
function handlePortfolioFields(){

    let isPageLoading = true
    // $ symbolically denotes that this is using jQuery
    const $seniorOfficial = django.jQuery("#id_senior_official");
    const seniorOfficialField = document.querySelector(".field-senior_official");
    const seniorOfficialAddress = seniorOfficialField.querySelector(".dja-address-contact-list");
    const seniorOfficialReadonly = seniorOfficialField.querySelector(".readonly");
    const $federalAgencyDropdown = django.jQuery("#id_federal_agency");
    const federalAgencyField = document.querySelector(".field-federal_agency");
    const organizationTypeField = document.querySelector(".field-organization_type");
    const organizationTypeReadonly = organizationTypeField.querySelector(".readonly");
    const organizationTypeDropdown = document.getElementById("id_organization_type");
    const organizationNameField = document.querySelector(".field-organization_name");
    const federalTypeField = document.querySelector(".field-federal_type");
    const urbanizationField = document.querySelector(".field-urbanization");
    const stateTerritoryDropdown = document.getElementById("id_state_territory");
    // consts for different urls
    const seniorOfficialAddUrl = document.getElementById("senior-official-add-url").value;

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

    function getSeniorOfficialFromAgency(agency) {
        const seniorOfficialApi = document.getElementById("senior_official_from_agency_json_url").value;
    
        return fetch(`${seniorOfficialApi}?agency_name=${agency}`)
            .then(response => {
                const statusCode = response.status;
                return response.json().then(data => ({ statusCode, data }));
            })
            .then(({ statusCode, data }) => {
                if (data.error) {
                    // Throw an error with status code and message
                    throw { statusCode, message: data.error };
                } else {
                    return data;
                }
            })
            .catch(error => {
                console.error("Error fetching senior official: ", error);
                throw error; // Re-throw for external handling
            });
    }
    
    function handleOrganizationTypeChange() {
        if (organizationTypeDropdown && organizationNameField) {
            let selectedValue = organizationTypeDropdown.value;
            if (selectedValue === "federal") {
                hideElement(organizationNameField);
                showElement(federalAgencyField);
                if (federalTypeField) {
                    showElement(federalTypeField);
                }
            } else {
                showElement(organizationNameField);
                hideElement(federalAgencyField);
                if (federalTypeField) {
                    hideElement(federalTypeField);
                }
            }
        }
    }

    function handleFederalAgencyChange() {
        if (!isPageLoading) {

            let selectedFederalAgency = $federalAgencyDropdown.find("option:selected").text();
            if (!selectedFederalAgency) {
                return;
            }

            // 1. Handle organization type
            let organizationTypeValue = organizationTypeDropdown ? organizationTypeDropdown.value : organizationTypeReadonly.innerText.toLowerCase();
            if (selectedFederalAgency !== "Non-Federal Agency") {
                if (organizationTypeValue !== "federal") {
                    if (organizationTypeDropdown){
                        organizationTypeDropdown.value = "federal";
                    } else {
                        organizationTypeReadonly.innerText = "Federal"
                    }
                }
            } else {
                if (organizationTypeValue === "federal") {
                    if (organizationTypeDropdown){
                        organizationTypeDropdown.value =  "";
                    } else {
                        organizationTypeReadonly.innerText =  "-"
                    }
                }
            }

            // 2. Handle organization type change side effects
            handleOrganizationTypeChange();

            // 3. Handle federal type
            getFederalTypeFromAgency(selectedFederalAgency).then((federalType) => updateReadOnly(federalType, '.field-federal_type'));
            
            // 4. Handle senior official
            hideElement(seniorOfficialAddress.parentElement);
            getSeniorOfficialFromAgency(selectedFederalAgency).then((data) => {
                // Update the "contact details" blurb beneath senior official
                updateContactInfo(data);
                showElement(seniorOfficialAddress.parentElement);
                // Get the associated senior official with this federal agency
                let seniorOfficialId = data.id;
                let seniorOfficialName = [data.first_name, data.last_name].join(" ");
                if ($seniorOfficial && $seniorOfficial.length > 0) {
                    // If the senior official is a dropdown field, edit that
                    updateSeniorOfficialDropdown($seniorOfficial, seniorOfficialId, seniorOfficialName);
                } else {
                    if (seniorOfficialReadonly) {
                        let seniorOfficialLink = `<a href=/admin/registrar/seniorofficial/${seniorOfficialId}/change/>${seniorOfficialName}</a>`
                        seniorOfficialReadonly.innerHTML = seniorOfficialName ? seniorOfficialLink : "-";
                    }
                }
            })
            .catch(error => {
                if (error.statusCode === 404) {
                    // Handle "not found" senior official
                    if ($seniorOfficial && $seniorOfficial.length > 0) {
                        $seniorOfficial.val("").trigger("change");
                    } else {
                        seniorOfficialReadonly.innerHTML = `<a href="${seniorOfficialAddUrl}">No senior official found. Create one now.</a>`;
                    }
                } else {
                    // Handle other errors
                    console.error("An error occurred:", error.message);
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

    function handleStateTerritoryChange() {
        let selectedValue = stateTerritoryDropdown.value;
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
        if (!seniorOfficialAddress) return;
    
        const titleSpan = seniorOfficialAddress.querySelector(".contact_info_title");
        const emailSpan = seniorOfficialAddress.querySelector(".contact_info_email");
        const phoneSpan = seniorOfficialAddress.querySelector(".contact_info_phone");
    
        if (titleSpan) { 
            titleSpan.textContent = data.title || "None";
        };

        // Update the email field and the content for the clipboard
        if (emailSpan) {
            let copyButton = seniorOfficialAddress.querySelector(".admin-icon-group");
            emailSpan.textContent = data.email || "None";
            if (data.email) {
                const clipboardInput = seniorOfficialAddress.querySelector(".admin-icon-group input");
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
        if (urbanizationField && stateTerritoryDropdown) {
            handleStateTerritoryChange();
        }
        handleOrganizationTypeChange();
    }

    function setEventListeners() {
        if ($federalAgencyDropdown && (organizationTypeDropdown || organizationTypeReadonly)) {
            $federalAgencyDropdown.on("change", function() {
                handleFederalAgencyChange();
            });
        }
        if (urbanizationField && stateTerritoryDropdown) {
            stateTerritoryDropdown.addEventListener("change", function() {
                handleStateTerritoryChange();
            });
        }
        organizationTypeDropdown.addEventListener("change", function() {
            handleOrganizationTypeChange();
        });
    }

    // Run initial setup functions
    initializePortfolioSettings();
    setEventListeners();
}

export function initDynamicPortfolioFields() {
    document.addEventListener('DOMContentLoaded', function() {
        let isPortfolioPage = document.getElementById("portfolio_form");
        if (isPortfolioPage) {
            handlePortfolioFields();
        }
    });
}
