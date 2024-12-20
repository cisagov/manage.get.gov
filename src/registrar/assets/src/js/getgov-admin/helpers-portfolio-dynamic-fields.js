import { hideElement, showElement } from './helpers-admin.js';

/**
 *
 * This function handles the portfolio selection as well as display of
 * portfolio-related fields in the DomainRequest Form.
 * 
 * IMPORTANT NOTE: The business logic in this method is based on dynamicPortfolioFields
*/
export function handlePortfolioSelection(
    portfolioDropdownSelector="#id_portfolio",
    suborgDropdownSelector="#id_sub_organization"
) {
    // These dropdown are select2 fields so they must be interacted with via jquery
    const portfolioDropdown = django.jQuery(portfolioDropdownSelector);
    const suborganizationDropdown = django.jQuery(suborgDropdownSelector);
    const suborganizationField = document.querySelector(".field-sub_organization");
    const requestedSuborganizationField = document.querySelector(".field-requested_suborganization");
    const suborganizationCity = document.querySelector(".field-suborganization_city");
    const suborganizationStateTerritory = document.querySelector(".field-suborganization_state_territory");
    const seniorOfficialField = document.querySelector(".field-senior_official");
    const otherEmployeesField = document.querySelector(".field-other_contacts");
    const noOtherContactsRationaleField = document.querySelector(".field-no_other_contacts_rationale");
    const cisaRepresentativeFirstNameField = document.querySelector(".field-cisa_representative_first_name");
    const cisaRepresentativeLastNameField = document.querySelector(".field-cisa_representative_last_name");
    const cisaRepresentativeEmailField = document.querySelector(".field-cisa_representative_email");
    const orgTypeFieldSet = document.querySelector(".field-is_election_board").parentElement;
    const orgTypeFieldSetDetails = orgTypeFieldSet.nextElementSibling;
    const orgNameFieldSet = document.querySelector(".field-organization_name").parentElement;
    const orgNameFieldSetDetails = orgNameFieldSet.nextElementSibling;
    const portfolioSeniorOfficialField = document.querySelector(".field-portfolio_senior_official");
    const portfolioSeniorOfficial = portfolioSeniorOfficialField.querySelector(".readonly");
    const portfolioSeniorOfficialAddress = portfolioSeniorOfficialField.querySelector(".dja-address-contact-list");
    const portfolioOrgTypeFieldSet = document.querySelector(".field-portfolio_organization_type").parentElement;
    const portfolioOrgType = document.querySelector(".field-portfolio_organization_type .readonly");
    const portfolioFederalTypeField = document.querySelector(".field-portfolio_federal_type");
    const portfolioFederalType = portfolioFederalTypeField.querySelector(".readonly");
    const portfolioOrgNameField = document.querySelector(".field-portfolio_organization_name")
    const portfolioOrgName = portfolioOrgNameField.querySelector(".readonly");
    const portfolioOrgNameFieldSet = portfolioOrgNameField.parentElement;
    const portfolioOrgNameFieldSetDetails = portfolioOrgNameFieldSet.nextElementSibling;
    const portfolioFederalAgencyField = document.querySelector(".field-portfolio_federal_agency");
    const portfolioFederalAgency = portfolioFederalAgencyField.querySelector(".readonly");
    const portfolioStateTerritory = document.querySelector(".field-portfolio_state_territory .readonly");
    const portfolioAddressLine1 = document.querySelector(".field-portfolio_address_line1 .readonly");
    const portfolioAddressLine2 = document.querySelector(".field-portfolio_address_line2 .readonly");
    const portfolioCity = document.querySelector(".field-portfolio_city .readonly");
    const portfolioZipcode = document.querySelector(".field-portfolio_zipcode .readonly");
    const portfolioUrbanizationField = document.querySelector(".field-portfolio_urbanization");
    const portfolioUrbanization = portfolioUrbanizationField.querySelector(".readonly");
    const portfolioJsonUrl = document.getElementById("portfolio_json_url")?.value || null;
    const rejectSuborganizationButtonFieldset = document.querySelector(".field-reject_suborganization_button");
    let isPageLoading = true;

   /**
     * Fetches portfolio data by ID using an AJAX call.
     *
     * @param {number|string} portfolio_id - The ID of the portfolio to retrieve.
     * @returns {Promise<Object|null>} - A promise that resolves to the portfolio data object if successful,
     *                                   or null if there was an error.
     *
     * This function performs an asynchronous fetch request to retrieve portfolio data.
     * If the request is successful, it returns the portfolio data as an object.
     * If an error occurs during the request or the data contains an error, it logs the error
     * to the console and returns null.
     */
    function getPortfolio(portfolio_id) {
        return fetch(`${portfolioJsonUrl}?id=${portfolio_id}`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error("Error in AJAX call: " + data.error);
                    return null;
                } else {
                    return data;
                }
            })
            .catch(error => {
                console.error("Error retrieving portfolio", error);
                return null;
            });
    }

    /**
     * Updates various UI elements with the data from a given portfolio object.
     *
     * @param {Object} portfolio - The portfolio data object containing values to populate in the UI.
     *
     * This function updates multiple fields in the UI to reflect data in the `portfolio` object:
     * - Clears and replaces selections in the `suborganizationDropdown` with values from `portfolio.suborganizations`.
     * - Calls `updatePortfolioSeniorOfficial` to set the senior official information.
     * - Sets the portfolio organization type, federal type, name, federal agency, and other address-related fields.
     *
     * The function expects that elements like `portfolioOrgType`, `portfolioFederalAgency`, etc., 
     * are already defined and accessible in the global scope.
     */
    function updatePortfolioFieldsData(portfolio) {
        // replace selections in suborganizationDropdown with
        // values in portfolio.suborganizations
        suborganizationDropdown.empty();
        // update portfolio senior official
        updatePortfolioSeniorOfficial(portfolio.senior_official);
        // update portfolio organization type
        portfolioOrgType.innerText = portfolio.organization_type;
        // update portfolio federal type
        portfolioFederalType.innerText = portfolio.federal_type
        // update portfolio organization name
        portfolioOrgName.innerText = portfolio.organization_name;
        // update portfolio federal agency
        portfolioFederalAgency.innerText = portfolio.federal_agency ? portfolio.federal_agency.agency : '';
        // update portfolio state
        portfolioStateTerritory.innerText = portfolio.state_territory;
        // update portfolio address line 1
        portfolioAddressLine1.innerText = portfolio.address_line1;
        // update portfolio address line 2
        portfolioAddressLine2.innerText = portfolio.address_line2;
        // update portfolio city
        portfolioCity.innerText = portfolio.city;
        // update portfolio zip code
        portfolioZipcode.innerText = portfolio.zipcode
        // update portfolio urbanization
        portfolioUrbanization.innerText = portfolio.urbanization;
    }

    /**
     * Updates the UI to display the senior official information from a given object.
     *
     * @param {Object} senior_official - The senior official's data object, containing details like 
     * first name, last name, and ID. If `senior_official` is null, displays a default message.
     *
     * This function:
     * - Displays the senior official's name as a link (if available) in the `portfolioSeniorOfficial` element.
     * - If a senior official exists, it sets `portfolioSeniorOfficialAddress` to show the official's contact info 
     *   and displays it by calling `updateSeniorOfficialContactInfo`.
     * - If no senior official is provided, it hides `portfolioSeniorOfficialAddress` and shows a "No senior official found." message.
     *
     * Dependencies:
     * - Expects the `portfolioSeniorOfficial` and `portfolioSeniorOfficialAddress` elements to be available globally.
     * - Uses `showElement` and `hideElement` for visibility control.
     */
    function updatePortfolioSeniorOfficial(senior_official) {
        if (senior_official) {
            let seniorOfficialName = [senior_official.first_name, senior_official.last_name].join(' ');
            let seniorOfficialLink = `<a href=/admin/registrar/seniorofficial/${senior_official.id}/change/ class='test'>${seniorOfficialName}</a>`
            portfolioSeniorOfficial.innerHTML = seniorOfficialName ? seniorOfficialLink : "-";
            updateSeniorOfficialContactInfo(portfolioSeniorOfficialAddress, senior_official);
            showElement(portfolioSeniorOfficialAddress);
        } else {
            portfolioSeniorOfficial.innerText = "No senior official found.";
            hideElement(portfolioSeniorOfficialAddress);
        }
    }

    /**
     * Populates and displays contact information for a senior official within a specified address field element.
     *
     * @param {HTMLElement} addressField - The DOM element containing contact info fields for the senior official.
     * @param {Object} senior_official - The senior official's data object, containing properties like title, email, and phone.
     *
     * This function:
     * - Sets the `title`, `email`, and `phone` fields in `addressField` to display the senior official's data.
     * - Updates the `titleSpan` with the official's title, or "None" if unavailable.
     * - Updates the `emailSpan` with the official's email, or "None" if unavailable. 
     * - If an email is provided, populates `hiddenInput` with the email for copying and shows the `copyButton`.
     * - If no email is provided, hides the `copyButton`.
     * - Updates the `phoneSpan` with the official's phone number, or "None" if unavailable.
     *
     * Dependencies:
     * - Uses `showElement` and `hideElement` to control visibility of the `copyButton`.
     * - Expects `addressField` to have specific classes (.contact_info_title, .contact_info_email, etc.) for query selectors to work.
     */
    function updateSeniorOfficialContactInfo(addressField, senior_official) {
        const titleSpan = addressField.querySelector(".contact_info_title");
        const emailSpan = addressField.querySelector(".contact_info_email");
        const phoneSpan = addressField.querySelector(".contact_info_phone");
        const hiddenInput = addressField.querySelector("input");
        const copyButton = addressField.querySelector(".admin-icon-group");
        if (titleSpan) { 
            titleSpan.textContent = senior_official.title || "None";
        };
        if (emailSpan) {
            emailSpan.textContent = senior_official.email || "None";
            if (senior_official.email) {
                hiddenInput.value = senior_official.email;
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
     * Dynamically updates the visibility of certain portfolio fields based on specific conditions.
     *
     * This function adjusts the display of fields within the portfolio UI based on:
     * - The presence of a senior official's contact information.
     * - The selected state or territory, affecting the visibility of the urbanization field.
     * - The organization type (Federal vs. non-Federal), toggling the visibility of related fields.
     *
     * Functionality:
     * 1. **Senior Official Contact Info Display**:
     *    - If `portfolioSeniorOfficial` contains "No additional contact information found",
     *      hides `portfolioSeniorOfficialAddress`; otherwise, shows it.
     *
     * 2. **Urbanization Field Display**:
     *    - Displays `portfolioUrbanizationField` only when the `portfolioStateTerritory` value is "PR" (Puerto Rico).
     *
     * 3. **Federal Organization Type Display**:
     *    - If `portfolioOrgType` is "Federal", hides `portfolioOrgNameField` and shows both `portfolioFederalAgencyField`
     *      and `portfolioFederalTypeField`.
     *    - If not Federal, shows `portfolioOrgNameField` and hides `portfolioFederalAgencyField` and `portfolioFederalTypeField`.
     *    - Certain text fields (Organization Type, Organization Name, Federal Type, Federal Agency) updated to links
     *      to edit the portfolio
     *
     * Dependencies:
     * - Expects specific elements to be defined globally (`portfolioSeniorOfficial`, `portfolioUrbanizationField`, etc.).
     * - Uses `showElement` and `hideElement` functions to control element visibility.
     */
    function updatePortfolioFieldsDataDynamicDisplay() {

        // Handle visibility of senior official's contact information
        if (portfolioSeniorOfficial.innerText.includes("No senior official found.")) {
            hideElement(portfolioSeniorOfficialAddress);
        } else {
            showElement(portfolioSeniorOfficialAddress);
        }

        // Handle visibility of urbanization field based on state/territory value
        let portfolioStateTerritoryValue = portfolioStateTerritory.innerText;
        if (portfolioStateTerritoryValue === "PR") {
            showElement(portfolioUrbanizationField);
        } else {
            hideElement(portfolioUrbanizationField);
        }

        // Handle visibility of fields based on organization type (Federal vs. others)
        if (portfolioOrgType.innerText === "Federal") {
            hideElement(portfolioOrgNameField);
            showElement(portfolioFederalAgencyField);
            showElement(portfolioFederalTypeField);
        } else {
            showElement(portfolioOrgNameField);
            hideElement(portfolioFederalAgencyField);
            hideElement(portfolioFederalTypeField);
        }

        // Modify the display of certain fields to convert them from text to links
        // to edit the portfolio
        let portfolio_id = portfolioDropdown.val();
        let portfolioEditUrl = `/admin/registrar/portfolio/${portfolio_id}/change/`;
        let portfolioOrgTypeValue = portfolioOrgType.innerText;
        portfolioOrgType.innerHTML = `<a href=${portfolioEditUrl}>${portfolioOrgTypeValue}</a>`;
        let portfolioOrgNameValue = portfolioOrgName.innerText;
        portfolioOrgName.innerHTML = `<a href=${portfolioEditUrl}>${portfolioOrgNameValue}</a>`;
        let portfolioFederalAgencyValue = portfolioFederalAgency.innerText;
        portfolioFederalAgency.innerHTML = `<a href=${portfolioEditUrl}>${portfolioFederalAgencyValue}</a>`;
        let portfolioFederalTypeValue = portfolioFederalType.innerText;
        if (portfolioFederalTypeValue !== '-')
            portfolioFederalType.innerHTML = `<a href=${portfolioEditUrl}>${portfolioFederalTypeValue}</a>`;

    }

    /**
     * Asynchronously updates portfolio fields in the UI based on the selected portfolio.
     *
     * This function first checks if the page is loading or if a portfolio selection is available
     * in the `portfolioDropdown`. If a portfolio is selected, it retrieves the portfolio data,
     * then updates the UI fields to display relevant data. If no portfolio is selected, it simply 
     * refreshes the UI field display without new data. The `isPageLoading` flag prevents
     * updates during page load.
     *
     * Workflow:
     * 1. **Check Page Loading**:
     *    - If `isPageLoading` is `true`, set it to `false` and exit to prevent redundant updates.
     *    - If `isPageLoading` is `false`, proceed with portfolio field updates.
     * 
     * 2. **Portfolio Selection**:
     *    - If a portfolio is selected (`portfolioDropdown.val()`), fetch the portfolio data.
     *    - Once data is fetched, run three update functions:
     *      - `updatePortfolioFieldsData`: Populates specific portfolio-related fields.
     *      - `updatePortfolioFieldsDisplay`: Handles the visibility of general portfolio fields.
     *      - `updatePortfolioFieldsDataDynamicDisplay`: Manages conditional display based on portfolio data.
     *    - If no portfolio is selected, only refreshes the field display using `updatePortfolioFieldsDisplay`.
     *
     * Dependencies:
     * - Expects global elements (`portfolioDropdown`, etc.) and `isPageLoading` flag to be defined.
     * - Assumes `getPortfolio`, `updatePortfolioFieldsData`, `updatePortfolioFieldsDisplay`, and `updatePortfolioFieldsDataDynamicDisplay` are available as functions.
     */
    async function updatePortfolioFields() {
        if (!isPageLoading) {
            if (portfolioDropdown.val()) {
                getPortfolio(portfolioDropdown.val()).then((portfolio) => {
                    updatePortfolioFieldsData(portfolio);
                    updatePortfolioFieldsDisplay();
                    updatePortfolioFieldsDataDynamicDisplay();
                });
            } else {
                updatePortfolioFieldsDisplay();
            }
        } else {
            isPageLoading = false;
        }
    }

    /**
     * Updates the Suborganization Dropdown with new data based on the provided portfolio ID.
     *
     * This function uses the Select2 jQuery plugin to update the dropdown by fetching suborganization
     * data relevant to the selected portfolio. Upon invocation, it checks if Select2 is already initialized
     * on `suborganizationDropdown` and destroys the existing instance to avoid duplication.
     * It then reinitializes Select2 with customized options for an AJAX request, allowing the user to search
     * and select suborganizations dynamically, with results filtered based on `portfolio_id`.
     *
     * Key workflow:
     * 1. **Document Ready**: Ensures that the function runs only once the DOM is fully loaded.
     * 2. **Check and Reinitialize Select2**:
     *    - If Select2 is already initialized, it’s destroyed to refresh with new options.
     *    - Select2 is reinitialized with AJAX settings for dynamic data fetching.
     * 3. **AJAX Options**:
     *    - **Data Function**: Prepares the query by capturing the user's search term (`params.term`)
     *      and the provided `portfolio_id` to filter relevant suborganizations.
     *    - **Data Type**: Ensures responses are returned as JSON.
     *    - **Delay**: Introduces a 250ms delay to prevent excessive requests on fast typing.
     *    - **Cache**: Enables caching to improve performance.
     * 4. **Theme and Placeholder**:
     *    - Sets the dropdown theme to ‘admin-autocomplete’ for consistent styling.
     *    - Allows clearing of the dropdown and displays a placeholder as defined in the HTML.
     *
     * Dependencies:
     * - Requires `suborganizationDropdown` element, the jQuery library, and the Select2 plugin.
     * - `portfolio_id` is passed to filter results relevant to a specific portfolio.
     */
    function updateSubOrganizationDropdown(portfolio_id) {
        django.jQuery(document).ready(function() {
            if (suborganizationDropdown.data('select2')) {
                suborganizationDropdown.select2('destroy');
            }
            // Reinitialize Select2 with the updated URL
            suborganizationDropdown.select2({
                ajax: {
                    data: function (params) {
                        var query = {
                            search: params.term,
                            portfolio_id: portfolio_id
                        }
                        return query;
                    },
                    dataType: 'json',
                    delay: 250,
                    cache: true
                },
                theme: 'admin-autocomplete',
                allowClear: true,
                placeholder: suborganizationDropdown.attr('data-placeholder')
            });
        });
    }

    /**
     * Updates the display of portfolio-related fields based on whether a portfolio is selected.
     *
     * This function controls the visibility of specific fields by showing or hiding them
     * depending on the presence of a selected portfolio ID in the dropdown. When a portfolio
     * is selected, certain fields are shown (like suborganizations and portfolio-related fields),
     * while others are hidden (like senior official and other employee-related fields).
     *
     * Workflow:
     * 1. **Retrieve Portfolio ID**: 
     *    - Fetches the selected value from `portfolioDropdown` to check if a portfolio is selected.
     *
     * 2. **Display Fields for Selected Portfolio**:
     *    - If a `portfolio_id` exists, it updates the `suborganizationDropdown` for the specific portfolio.
     *    - Shows or hides various fields to display only relevant portfolio information:
     *      - Shows `suborganizationField`, `portfolioSeniorOfficialField`, and fields related to the portfolio organization.
     *      - Hides fields that are not applicable when a portfolio is selected, such as `seniorOfficialField` and `otherEmployeesField`.
     *
     * 3. **Display Fields for No Portfolio Selected**:
     *    - If no portfolio is selected (i.e., `portfolio_id` is falsy), it reverses the visibility:
     *      - Hides `suborganizationField` and other portfolio-specific fields.
     *      - Shows fields that are applicable when no portfolio is selected, such as the `seniorOfficialField`.
     *
     * Dependencies:
     * - `portfolioDropdown` is assumed to be a dropdown element containing portfolio IDs.
     * - `showElement` and `hideElement` utility functions are used to control element visibility.
     * - Various global field elements (e.g., `suborganizationField`, `seniorOfficialField`, `portfolioOrgTypeFieldSet`) are used.
     */
    function updatePortfolioFieldsDisplay() {
        // Retrieve the selected portfolio ID
        let portfolio_id = portfolioDropdown.val();

        if (portfolio_id) {
            // A portfolio is selected - update suborganization dropdown and show/hide relevant fields

            // Update suborganization dropdown for the selected portfolio
            updateSubOrganizationDropdown(portfolio_id);

            // Show fields relevant to a selected portfolio
            showElement(suborganizationField);
            hideElement(seniorOfficialField);
            showElement(portfolioSeniorOfficialField);

            // Hide fields not applicable when a portfolio is selected
            if (otherEmployeesField) hideElement(otherEmployeesField);
            if (noOtherContactsRationaleField) hideElement(noOtherContactsRationaleField);
            hideElement(cisaRepresentativeFirstNameField);
            hideElement(cisaRepresentativeLastNameField);
            hideElement(cisaRepresentativeEmailField);
            hideElement(orgTypeFieldSet);
            hideElement(orgTypeFieldSetDetails);
            hideElement(orgNameFieldSet);
            hideElement(orgNameFieldSetDetails);

            // Show portfolio-specific fields
            showElement(portfolioOrgTypeFieldSet);
            showElement(portfolioOrgNameFieldSet);
            showElement(portfolioOrgNameFieldSetDetails);
        } else {
            // No portfolio is selected - reverse visibility of fields

            // Hide suborganization field as no portfolio is selected
            hideElement(suborganizationField);

            // Show fields that are relevant when no portfolio is selected
            showElement(seniorOfficialField);
            hideElement(portfolioSeniorOfficialField);
            if (otherEmployeesField) showElement(otherEmployeesField);
            if (noOtherContactsRationaleField) showElement(noOtherContactsRationaleField);
            showElement(cisaRepresentativeFirstNameField);
            showElement(cisaRepresentativeLastNameField);
            showElement(cisaRepresentativeEmailField);

            // Show organization type and name fields
            showElement(orgTypeFieldSet);
            showElement(orgTypeFieldSetDetails);
            showElement(orgNameFieldSet);
            showElement(orgNameFieldSetDetails);

            // Hide portfolio-specific fields that aren’t applicable
            hideElement(portfolioOrgTypeFieldSet);
            hideElement(portfolioOrgNameFieldSet);
            hideElement(portfolioOrgNameFieldSetDetails);
        }

        updateSuborganizationFieldsDisplay();

    }

    /**
     * Updates the visibility of suborganization-related fields based on the selected value in the suborganization dropdown.
     * 
     * If a suborganization is selected:
     *   - Hides the fields related to requesting a new suborganization (`requestedSuborganizationField`).
     *   - Hides the city (`suborganizationCity`) and state/territory (`suborganizationStateTerritory`) fields for the suborganization.
     * 
     * If no suborganization is selected:
     *   - Shows the fields for requesting a new suborganization (`requestedSuborganizationField`).
     *   - Displays the city (`suborganizationCity`) and state/territory (`suborganizationStateTerritory`) fields.
     * 
     * This function ensures the form dynamically reflects whether a specific suborganization is being selected or requested.
     */
    function updateSuborganizationFieldsDisplay() {
        let portfolio_id = portfolioDropdown.val();
        let suborganization_id = suborganizationDropdown.val();

        if (portfolio_id && !suborganization_id) {
            // Show suborganization request fields
            if (requestedSuborganizationField) showElement(requestedSuborganizationField);
            if (suborganizationCity) showElement(suborganizationCity);
            if (suborganizationStateTerritory) showElement(suborganizationStateTerritory);
            
            // Initially show / hide the clear button only if there is data to clear
            let requestedSuborganizationField = document.getElementById("id_requested_suborganization");
            let suborganizationCity = document.getElementById("id_suborganization_city");
            let suborganizationStateTerritory = document.getElementById("id_suborganization_state_territory");
            if (!requestedSuborganizationField || !suborganizationCity || !suborganizationStateTerritory) {
                return;
            }

            if (requestedSuborganizationField.value || suborganizationCity.value || suborganizationStateTerritory.value) {
                showElement(rejectSuborganizationButtonFieldset);
            }else {
                hideElement(rejectSuborganizationButtonFieldset);
            }
        } else {
            // Hide suborganization request fields if suborganization is selected
            if (requestedSuborganizationField) hideElement(requestedSuborganizationField);
            if (suborganizationCity) hideElement(suborganizationCity);
            if (suborganizationStateTerritory) hideElement(suborganizationStateTerritory);
            hideElement(rejectSuborganizationButtonFieldset);  
        }
    }

    /**
     * Initializes necessary data and display configurations for the portfolio fields.
     */
    function initializePortfolioSettings() {
        // Update the visibility of portfolio-related fields based on current dropdown selection.
        updatePortfolioFieldsDisplay();

        // Dynamically adjust the display of certain fields based on the selected portfolio's characteristics.
        updatePortfolioFieldsDataDynamicDisplay();
    }

    /**
     * Sets event listeners for key UI elements.
     */
    function setEventListeners() {
        // When the `portfolioDropdown` selection changes, refresh the displayed portfolio fields.
        portfolioDropdown.on("change", updatePortfolioFields);
        // When the 'suborganizationDropdown' selection changes
        suborganizationDropdown.on("change", updateSuborganizationFieldsDisplay);
    }

    // Run initial setup functions
    initializePortfolioSettings();
    setEventListeners();
}
