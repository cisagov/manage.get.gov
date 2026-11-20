import { hideElement, showElement } from './helpers-admin.js';

/**
 * A function for dynamically changing some fields on the portfolio admin model
 * IMPORTANT NOTE: The business logic in this function is related to handlePortfolioSelection
*/
function handlePortfolioFields(){

    let isPageLoading = true
    // $ symbolically denotes that this is using jQuery
    const $seniorOfficialDropdown = django.jQuery("#id_senior_official");
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
    const stateTerritoryField = document.querySelector(".field-state_territory");
    const stateTerritoryReadonly = stateTerritoryField.querySelector(".readonly");
    const seniorOfficialAddUrl = document.getElementById("senior-official-add-url").value;
    const seniorOfficialApi = document.getElementById("senior_official_from_agency_json_url").value;
    const federalPortfolioApi = document.getElementById("federal_and_portfolio_types_from_agency_json_url").value;
    const tribeDetailsApi = document.getElementById("tribe_details_json_url").value;
    const savedTribeSelection = document.getElementById("portfolio-tribe").value;
    const tribeDropdown = document.getElementById("id_tribe");
    // Mailing address fields (for tribes)
    const addressLine1Input = document.getElementById("id_address_line1");
    const addressLine2Input = document.getElementById("id_address_line2");
    const cityInput = document.getElementById("id_city");
    const zipcodeInput = document.getElementById("id_zipcode");
    const urbanizationInput = document.getElementById("id_urbanization");

    /**
     * Fetches federal type data based on a selected agency using an AJAX call.
     *
     * @param {string} agency
     * @returns {Promise<Object|null>} - A promise that resolves to the portfolio data object if successful,
     *                                   or null if there was an error.
     */
    function getFederalTypeFromAgency(agency) {
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

    /**
     * Fetches senior official contact data based on a selected agency using an AJAX call.
     *
     * @param {string} agency
     * @returns {Promise<Object|null>} - A promise that resolves to the portfolio data object if successful,
     *                                   or null if there was an error.
     */
    function getSeniorOfficialFromAgency(agency) {
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

    /**
     * Fetches tribe details based on the selected federal or state tribe using an AJAX call.
     *
     * @param {string} selectedTribe - The selection, such as "federal:12" or "state:34".
     * @returns {Promise<Object>} - The tribe details, or a rejected promise when the lookup fails.
     */
    function getTribeDetails(selectedTribe) {
        const [tribeType, tribeId] = selectedTribe.split(":", 2);
        const params = new URLSearchParams({
            tribe_type: tribeType,
            tribe_id: tribeId,
        });

        return fetch(`${tribeDetailsApi}?${params}`)
            .then(response => {
                const statusCode = response.status;
                return response.json().then(data => ({ statusCode, data }));
            })
            .then(({ statusCode, data }) => {
                if (data.error) {
                    throw { statusCode, message: data.error };
                }
                return data;
            });
    }

    /** Return the selected tribe */
    function getSelectedTribe() {
        if (tribeDropdown) {
            return tribeDropdown.value;
        }
        return savedTribeSelection;
    }

    /**
     * Handles the side effects of change on the organization type field
     *
     * 1. If selection is federal, hide org name, show federal agency, show federal type if applicable
     * 2. else show org name, hide federal agency, hide federal type if applicable
     */
    function handleOrganizationTypeChange() {
        if (organizationTypeField && organizationNameField) {
            let selectedValue = organizationTypeDropdown ? organizationTypeDropdown.value : organizationTypeReadonly.innerText;
            if (selectedValue === "federal" || selectedValue === "Federal") {
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
        handleTribalMailingAddress();
    }

    /** Keep the address present when switching away from a tribe. */
    function handleTribalMailingAddress() {
        let organizationType = "";
        if (organizationTypeDropdown) {
            organizationType = organizationTypeDropdown.value;
        } else if (organizationTypeReadonly) {
            organizationType = organizationTypeReadonly.innerText;
        }
        organizationType = organizationType.trim().toLowerCase();

        const selectedTribe = getSelectedTribe();
        let useTribalMailingAddress = false;
        if (organizationType === "tribal" && selectedTribe) {
            useTribalMailingAddress = true;
        }

        // Selects do not support readOnly. The form also ignores submitted Tribal address values.
        if (stateTerritoryDropdown) {
            stateTerritoryDropdown.disabled = useTribalMailingAddress;
        }

        const mailingAddressTextInputs = [
            addressLine1Input,
            addressLine2Input,
            cityInput,
            zipcodeInput,
            urbanizationInput,
        ];

        for (const addressInput of mailingAddressTextInputs) {
            if (!addressInput) {
                // Could happen for read-only
                continue;
            }

            addressInput.disabled = false;
            addressInput.readOnly = useTribalMailingAddress;
        }

        if (useTribalMailingAddress) {
            getTribeDetails(selectedTribe).then((tribeDetails) => {
                // Since we just did an AJAX call, ensure values still match (form could have changed during call)
                if (getSelectedTribe() !== selectedTribe) {
                    return;
                }
                if (organizationTypeDropdown && organizationTypeDropdown.value !== "tribal") {
                    return;
                }

                updateTribalMailingAddress(tribeDetails.mailing_address);
            }).catch(error => {
                console.error("Error fetching tribe details: ", error);
            });
        }
    }

    /**
     * Handles the side effects of change on the federal agency field
     *
     * 1. handle org type dropdown or readonly
     * 2. call handleOrganizationTypeChange
     * 3. call getFederalTypeFromAgency and update federal type
     * 4. call getSeniorOfficialFromAgency and update the SO fieldset
     */
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
            getSeniorOfficialFromAgency(selectedFederalAgency).then((senior_official) => {
                // Update the "contact details" blurb beneath senior official
                updateSeniorOfficialContactInfo(senior_official);
                showElement(seniorOfficialAddress.parentElement);
                // Get the associated senior official with this federal agency
                let seniorOfficialId = senior_official.id;
                let seniorOfficialName = [senior_official.first_name, senior_official.last_name].join(" ");
                if ($seniorOfficialDropdown && $seniorOfficialDropdown.length > 0) {
                    // If the senior official is a dropdown field, edit that
                    updateSeniorOfficialDropdown(seniorOfficialId, seniorOfficialName);
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
                    if ($seniorOfficialDropdown && $seniorOfficialDropdown.length > 0) {
                        $seniorOfficialDropdown.val("").trigger("change");
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

    /**
     * Helper for updating federal type field
     */
    function updateSeniorOfficialDropdown(seniorOfficialId, seniorOfficialName) {
        if (!seniorOfficialId || !seniorOfficialName || !seniorOfficialName.trim()){
            // Clear the field if the SO doesn't exist
            $seniorOfficialDropdown.val("").trigger("change");
            return;
        }
        // Add the senior official to the dropdown.
        // This format supports select2 - if we decide to convert this field in the future.
        if ($seniorOfficialDropdown.find(`option[value='${seniorOfficialId}']`).length) {
            // Select the value that is associated with the current Senior Official.
            $seniorOfficialDropdown.val(seniorOfficialId).trigger("change");
        } else {
            // Create a DOM Option that matches the desired Senior Official. Then append it and select it.
            let userOption = new Option(seniorOfficialName, seniorOfficialId, true, true);
            $seniorOfficialDropdown.append(userOption).trigger("change");
        }
    }

    /** For tribes, update address components. */
    function updateTribalMailingAddress(mailingAddress) {
        if (stateTerritoryDropdown) {
            stateTerritoryDropdown.value = mailingAddress.state_territory;
        }
        if (addressLine1Input) {
            addressLine1Input.value = mailingAddress.address_line1;
        }
        if (addressLine2Input) {
            addressLine2Input.value = mailingAddress.address_line2;
        }
        if (cityInput) {
            cityInput.value = mailingAddress.city;
        }
        if (zipcodeInput) {
            zipcodeInput.value = mailingAddress.zipcode;
        }
        if (urbanizationInput) {
            urbanizationInput.value = mailingAddress.urbanization;
        }
        if (urbanizationField && stateTerritoryField) {
            handleStateTerritoryChange();
        }
    }

    /**
     * Handle urbanization
     */
    function handleStateTerritoryChange() {
        let selectedValue = stateTerritoryDropdown ? stateTerritoryDropdown.value : stateTerritoryReadonly.innerText;
        if (selectedValue === "PR" || selectedValue === "Puerto Rico (PR)") {
            showElement(urbanizationField)
        } else {
            hideElement(urbanizationField)
        }
    }

    /**
     * Helper for updating senior official dropdown
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

    /**
     * Helper for updating senior official contact info
     */
    function updateSeniorOfficialContactInfo(senior_official) {
        if (!seniorOfficialAddress) return;
        const titleSpan = seniorOfficialAddress.querySelector(".contact_info_title");
        const emailSpan = seniorOfficialAddress.querySelector(".contact_info_email");
        const phoneSpan = seniorOfficialAddress.querySelector(".contact_info_phone");
        if (titleSpan) {
            titleSpan.textContent = senior_official.title || "None";
        };
        // Update the email field and the content for the clipboard
        if (emailSpan) {
            let copyButton = seniorOfficialAddress.querySelector(".admin-icon-group");
            emailSpan.textContent = senior_official.email || "None";
            if (senior_official.email) {
                const clipboardInput = seniorOfficialAddress.querySelector(".admin-icon-group input");
                if (clipboardInput) {
                    clipboardInput.value = senior_official.email;
                };
                showElement(copyButton);
            }else {
                hideElement(copyButton);
            }
        }
        if (phoneSpan) {
            phoneSpan.textContent = senior_official.phone || "None";
        };
    }

    /**
     * Initializes necessary data and display configurations for the portfolio fields.
     */
    function initializePortfolioSettings() {
        if (urbanizationField && stateTerritoryField) {
            handleStateTerritoryChange();
        }
        handleOrganizationTypeChange();
    }

    /**
     * Sets event listeners for key UI elements.
     */
    function setEventListeners() {
        if (tribeDropdown) {
            django.jQuery(tribeDropdown).on("change", function() {
                handleTribalMailingAddress();
            });
        }
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
        if (organizationTypeDropdown) {
            organizationTypeDropdown.addEventListener("change", function() {
                handleOrganizationTypeChange();
            });
        }
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
