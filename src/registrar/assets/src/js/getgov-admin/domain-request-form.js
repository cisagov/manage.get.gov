import { hideElement, showElement, addOrRemoveSessionBoolean, announceForScreenReaders } from './helpers-admin.js';
import { handlePortfolioSelection } from './helpers-portfolio-dynamic-fields.js';

function displayModalOnDropdownClick(linkClickedDisplaysModal, statusDropdown, actionButton, valueToCheck){

    // If these exist all at the same time, we're on the right page
    if (linkClickedDisplaysModal && statusDropdown && statusDropdown.value){
        
        // Set the previous value in the event the user cancels.
        let previousValue = statusDropdown.value;
        if (actionButton){

            // Otherwise, if the confirmation buttion is pressed, set it to that
            actionButton.addEventListener('click', function() {
                // Revert the dropdown to its previous value
                statusDropdown.value = valueToCheck;
            });
        } else {
            console.warn("displayModalOnDropdownClick() -> Cancel button was null");
        }

        // Add a change event listener to the dropdown.
        statusDropdown.addEventListener('change', function() {
            // Check if "Ineligible" is selected
            if (this.value && this.value.toLowerCase() === valueToCheck) {
                // Set the old value in the event the user cancels,
                // or otherwise exists the dropdown.
                statusDropdown.value = previousValue;

                // Display the modal.
                linkClickedDisplaysModal.click();
            }
        });
    }
}

/**
 * A function for DomainRequest to hook a modal to a dropdown option.
 * This intentionally does not interact with createPhantomModalFormButtons()
 * When the status dropdown is clicked and is set to "ineligible", toggle a confirmation dropdown.
*/
export function initIneligibleModal(){
    // Grab the invisible element that will hook to the modal.
    // This doesn't technically need to be done with one, but this is simpler to manage.
    let modalButton = document.getElementById("invisible-ineligible-modal-toggler");
    let statusDropdown = document.getElementById("id_status");

    // Because the modal button does not have the class "dja-form-placeholder",
    // it will not be affected by the createPhantomModalFormButtons() function.
    let actionButton = document.querySelector('button[name="_set_domain_request_ineligible"]');
    let valueToCheck = "ineligible";
    displayModalOnDropdownClick(modalButton, statusDropdown, actionButton, valueToCheck);
}

/**
 * A function for the "Assign to me" button under the investigator field in DomainRequests.
 * This field uses the "select2" selector, rather than the default. 
 * To perform data operations on this - we need to use jQuery rather than vanilla js. 
*/
export function initAssignToMe() {
    if (document.getElementById("id_investigator") && django && django.jQuery) {
        let selector = django.jQuery("#id_investigator");
        let assignSelfButton = document.querySelector("#investigator__assign_self");
        if (!selector || !assignSelfButton) {
            return;
        }

        let currentUserId = assignSelfButton.getAttribute("data-user-id");
        let currentUserName = assignSelfButton.getAttribute("data-user-name");
        if (!currentUserId || !currentUserName){
            console.error("Could not assign current user: no values found.");
            return;
        }

        // Hook a click listener to the "Assign to me" button.
        // Logic borrowed from here: https://select2.org/programmatic-control/add-select-clear-items#create-if-not-exists
        assignSelfButton.addEventListener("click", function() {
            if (selector.find(`option[value='${currentUserId}']`).length) {
                // Select the value that is associated with the current user.
                selector.val(currentUserId).trigger("change");
            } else { 
                // Create a DOM Option that matches the desired user. Then append it and select it.
                let userOption = new Option(currentUserName, currentUserId, true, true);
                selector.append(userOption).trigger("change");
            }
        });

        // Listen to any change events, and hide the parent container if investigator has a value.
        selector.on('change', function() {
            // The parent container has display type flex.
            assignSelfButton.parentElement.style.display = this.value === currentUserId ? "none" : "flex";
        });
    }
}

/**
 * A function that hides and shows approved domain select2 row in domain request
 * conditionally based on the Status field selection. If Approved, show. If not Approved,
 * don't show.
*/
export function initApprovedDomain() {
    document.addEventListener('DOMContentLoaded', function() {
        const domainRequestForm = document.getElementById("domainrequest_form");
        if (!domainRequestForm) {
            return;
        }

        const statusToCheck = "approved";  // when checking against a select
        const readonlyStatusToCheck = "Approved";  // when checking against a readonly div display value
        const statusSelect = document.getElementById("id_status");
        const statusField = document.querySelector("field-status");
        const sessionVariableName = "showApprovedDomain";
        let approvedDomainFormGroup = document.querySelector(".field-approved_domain");

        function updateFormGroupVisibility(showFormGroups) {
            if (showFormGroups) {
                showElement(approvedDomainFormGroup);
            } else {
                hideElement(approvedDomainFormGroup);
            }
        }

        // Handle showing/hiding the related fields on page load.
        function initializeFormGroups() {
            // Status is either in a select or in a readonly div. Both
            // cases are handled below.
            let isStatus = false;
            if (statusSelect) {
                isStatus = statusSelect.value == statusToCheck;
            } else {
                // statusSelect does not exist, indicating readonly
                if (statusField) {
                    let readonlyDiv = statusField.querySelector("div.readonly");
                    let readonlyStatusText = readonlyDiv.textContent.trim();
                    isStatus = readonlyStatusText == readonlyStatusToCheck;
                }
            }

            // Initial handling of these groups.
            updateFormGroupVisibility(isStatus);

            if (statusSelect) {
                // Listen to change events and handle rejectionReasonFormGroup display, then save status to session storage
                statusSelect.addEventListener('change', () => {
                    // Show the approved if the status is what we expect.
                    isStatus = statusSelect.value == statusToCheck;
                    updateFormGroupVisibility(isStatus);
                    addOrRemoveSessionBoolean(sessionVariableName, isStatus);
                });
            }
            
            // Listen to Back/Forward button navigation and handle approvedDomainFormGroup display based on session storage
            // When you navigate using forward/back after changing status but not saving, when you land back on the DA page the
            // status select will say (for example) Rejected but the selected option can be something else. To manage the show/hide
            // accurately for this edge case, we use cache and test for the back/forward navigation.
            const observer = new PerformanceObserver((list) => {
                list.getEntries().forEach((entry) => {
                    if (entry.type === "back_forward") {
                        let showTextAreaFormGroup = sessionStorage.getItem(sessionVariableName) !== null;
                        updateFormGroupVisibility(showTextAreaFormGroup);
                    }
                });
            });
            observer.observe({ type: "navigation" });
        }

        initializeFormGroups();
    });
}

/**
 * A function for copy summary button
*/
export function initCopyRequestSummary() {
    const copyButton = document.getElementById('id-copy-to-clipboard-summary');

    if (copyButton) {
        copyButton.addEventListener('click', function() {
            /// Generate a rich HTML summary text and copy to clipboard

            //------ Organization Type
            const organizationTypeElement = document.getElementById('id_organization_type');
            const organizationType = organizationTypeElement.options[organizationTypeElement.selectedIndex].text;

            //------ Alternative Domains
            const alternativeDomainsDiv = document.querySelector('.form-row.field-alternative_domains .readonly');
            const alternativeDomainslinks = alternativeDomainsDiv.querySelectorAll('a');
            const alternativeDomains = Array.from(alternativeDomainslinks).map(link => link.textContent);

            //------ Existing Websites
            const existingWebsitesDiv = document.querySelector('.form-row.field-current_websites .readonly');
            const existingWebsiteslinks = existingWebsitesDiv.querySelectorAll('a');
            const existingWebsites = Array.from(existingWebsiteslinks).map(link => link.textContent);

            //------ Additional Contacts
            // 1 - Create a hyperlinks map so we can display contact details and also link to the contact
            const otherContactsDiv = document.querySelector('.form-row.field-other_contacts .readonly');
            let otherContactLinks = [];
            const nameToUrlMap = {};
            if (otherContactsDiv) {
                otherContactLinks = otherContactsDiv.querySelectorAll('a');
                otherContactLinks.forEach(link => {
                const name = link.textContent.trim();
                const url = link.href;
                nameToUrlMap[name] = url;
                });
            }
        
            // 2 - Iterate through contact details and assemble html for summary
            let otherContactsSummary = ""
            const bulletList = document.createElement('ul');

            // CASE 1 - Contacts are not in a table (this happens if there is only one or two other contacts)
            const contacts = document.querySelectorAll('.field-other_contacts .dja-detail-list dd');
            if (contacts) {
                contacts.forEach(contact => {
                    // Check if the <dl> element is not empty
                    const name = contact.querySelector('a.contact_info_name')?.innerText;
                    const title = contact.querySelector('span.contact_info_title')?.innerText;
                    const email = contact.querySelector('span.contact_info_email')?.innerText;
                    const phone = contact.querySelector('span.contact_info_phone')?.innerText;
                    const url = nameToUrlMap[name] || '#';
                    // Format the contact information
                    const listItem = document.createElement('li');
                    listItem.innerHTML = `<a href="${url}">${name}</a>, ${title}, ${email}, ${phone}`;
                    bulletList.appendChild(listItem);
                });

            }

            // CASE 2 - Contacts are in a table (this happens if there is more than 2 contacts)
            const otherContactsTable = document.querySelector('.form-row.field-other_contacts table tbody');
            if (otherContactsTable) {
                const otherContactsRows = otherContactsTable.querySelectorAll('tr');
                otherContactsRows.forEach(contactRow => {
                // Extract the contact details
                const name = contactRow.querySelector('th').textContent.trim();
                const title = contactRow.querySelectorAll('td')[0].textContent.trim();
                const email = contactRow.querySelectorAll('td')[1].textContent.trim();
                const phone = contactRow.querySelectorAll('td')[2].textContent.trim();
                const url = nameToUrlMap[name] || '#';
                // Format the contact information
                const listItem = document.createElement('li');
                listItem.innerHTML = `<a href="${url}">${name}</a>, ${title}, ${email}, ${phone}`;
                bulletList.appendChild(listItem);
                });
            }
            otherContactsSummary += bulletList.outerHTML;


            //------ Requested Domains
            const requestedDomainElement = document.getElementById('id_requested_domain');
            // We have to account for different superuser and analyst markups
            const requestedDomain = requestedDomainElement.options 
                ? requestedDomainElement.options[requestedDomainElement.selectedIndex].text 
                : requestedDomainElement.text;

            //------ Submitter
            // Function to extract text by ID and handle missing elements
            function extractTextById(id, divElement) {
                if (divElement) {
                    const element = divElement.querySelector(`#${id}`);
                    return element ? ", " + element.textContent.trim() : '';
                }
                return '';
            }

            //------ Senior Official
            const seniorOfficialDiv = document.querySelector('.form-row.field-senior_official');
            const seniorOfficialElement = document.getElementById('id_senior_official');
            const seniorOfficialName = seniorOfficialElement.options[seniorOfficialElement.selectedIndex].text;
            const seniorOfficialTitle = seniorOfficialDiv.querySelector('.contact_info_title');
            const seniorOfficialEmail = seniorOfficialDiv.querySelector('.contact_info_email');
            const seniorOfficialPhone = seniorOfficialDiv.querySelector('.contact_info_phone');
            let seniorOfficialInfo = `${seniorOfficialName}${seniorOfficialTitle}${seniorOfficialEmail}${seniorOfficialPhone}`;

            const html_summary = `<strong>Recommendation:</strong></br>` +
                            `<strong>Organization Type:</strong> ${organizationType}</br>` +
                            `<strong>Requested Domain:</strong> ${requestedDomain}</br>` +
                            `<strong>Current Websites:</strong> ${existingWebsites.join(', ')}</br>` +
                            `<strong>Rationale:</strong></br>` +
                            `<strong>Alternative Domains:</strong> ${alternativeDomains.join(', ')}</br>` +
                            `<strong>Senior Official:</strong> ${seniorOfficialInfo}</br>` +
                            `<strong>Other Employees:</strong> ${otherContactsSummary}</br>`;
            
            //Replace </br> with \n, then strip out all remaining html tags (replace <...> with '')
            const plain_summary = html_summary.replace(/<\/br>|<br>/g, '\n').replace(/<\/?[^>]+(>|$)/g, '');

            // Create Blobs with the summary content
            const html_blob = new Blob([html_summary], { type: 'text/html' });
            const plain_blob = new Blob([plain_summary], { type: 'text/plain' });

            // Create a ClipboardItem with the Blobs
            const clipboardItem = new ClipboardItem({
                'text/html': html_blob,
                'text/plain': plain_blob
            });

            // Write the ClipboardItem to the clipboard
            navigator.clipboard.write([clipboardItem]).then(() => {
                // Change the icon to a checkmark on successful copy
                let buttonIcon = copyButton.querySelector('use');
                if (buttonIcon) {
                    let currentHref = buttonIcon.getAttribute('xlink:href');
                    let baseHref = currentHref.split('#')[0];

                    // Append the new icon reference
                    buttonIcon.setAttribute('xlink:href', baseHref + '#check');

                    // Change the button text
                    let nearestSpan = copyButton.querySelector("span");
                    let original_text = nearestSpan.innerText;
                    nearestSpan.innerText = "Copied to clipboard";

                    setTimeout(function() {
                        // Change back to the copy icon
                        buttonIcon.setAttribute('xlink:href', currentHref); 
                        nearestSpan.innerText = original_text;
                    }, 2000);

                }
                console.log('Summary copied to clipboard successfully!');
            }).catch(err => {
                console.error('Failed to copy text: ', err);
            });
        });
    }
}

class CustomizableEmailBase {
    /**
     * @param {Object} config - must contain the following:
     * @property {HTMLElement} dropdown - The dropdown element.
     * @property {HTMLElement} textarea - The textarea element.
     * @property {HTMLElement} lastSentEmailContent - The last sent email content element.
     * @property {HTMLElement} textAreaFormGroup - The form group for the textarea.
     * @property {HTMLElement} dropdownFormGroup - The form group for the dropdown.
     * @property {HTMLElement} modalConfirm - The confirm button in the modal.
     * @property {string} apiUrl - The API URL for fetching email content.
     * @property {string} statusToCheck - The status to check against. Used for show/hide on textAreaFormGroup/dropdownFormGroup.
     * @property {string} readonlyStatusToCheck - The status to check against when readonly. Used for show/hide on textAreaFormGroup/dropdownFormGroup.
     * @property {string} sessionVariableName - The session variable name. Used for show/hide on textAreaFormGroup/dropdownFormGroup.
     * @property {string} apiErrorMessage - The error message that the ajax call returns.
     */
    constructor(config) {
        this.config = config;        
        this.dropdown = config.dropdown;
        this.textarea = config.textarea;
        this.lastSentEmailContent = config.lastSentEmailContent;
        this.apiUrl = config.apiUrl;
        this.apiErrorMessage = config.apiErrorMessage;
        this.modalConfirm = config.modalConfirm;

        // These fields are hidden/shown on pageload depending on the current status
        this.textAreaFormGroup = config.textAreaFormGroup;
        this.dropdownFormGroup = config.dropdownFormGroup;
        this.statusToCheck = config.statusToCheck;
        this.readonlyStatusToCheck = config.readonlyStatusToCheck;
        this.sessionVariableName = config.sessionVariableName;

        // Non-configurable variables
        this.statusSelect = document.getElementById("id_status");
        this.domainRequestId = this.dropdown ? document.getElementById("domain_request_id").value : null
        this.initialDropdownValue = this.dropdown ? this.dropdown.value : null;
        this.initialEmailValue = this.textarea ? this.textarea.value : null;

        // Find other fields near the textarea 
        const parentDiv = this.textarea ? this.textarea.closest(".flex-container") : null;
        this.directEditButton = parentDiv ? parentDiv.querySelector(".edit-email-button") : null;
        this.modalTrigger = parentDiv ? parentDiv.querySelector(".edit-button-modal-trigger") : null;

        this.textareaPlaceholder = parentDiv ? parentDiv.querySelector(".custom-email-placeholder") : null;
        this.formLabel = this.textarea ? document.querySelector(`label[for="${this.textarea.id}"]`) : null;

        this.isEmailAlreadySentConst;
        if (this.lastSentEmailContent && this.textarea) {
            this.isEmailAlreadySentConst = this.lastSentEmailContent.value.replace(/\s+/g, '') === this.textarea.value.replace(/\s+/g, '');
        }

    }

    // Handle showing/hiding the related fields on page load.
    initializeFormGroups() {
        let isStatus = false;
        if (this.statusSelect) {
            isStatus = this.statusSelect.value == this.statusToCheck;
        } else {
            // statusSelect does not exist, indicating readonly
            if (this.dropdownFormGroup) {
                let readonlyDiv = this.dropdownFormGroup.querySelector("div.readonly");
                let readonlyStatusText = readonlyDiv.textContent.trim();
                isStatus = readonlyStatusText == this.readonlyStatusToCheck;
            }
        }

        // Initial handling of these groups.
        this.updateFormGroupVisibility(isStatus);

        if (this.statusSelect) {
            // Listen to change events and handle rejectionReasonFormGroup display, then save status to session storage
            this.statusSelect.addEventListener('change', () => {
                // Show the action needed field if the status is what we expect.
                // Then track if its shown or hidden in our session cache.
                isStatus = this.statusSelect.value == this.statusToCheck;
                this.updateFormGroupVisibility(isStatus);
                addOrRemoveSessionBoolean(this.sessionVariableName, isStatus);
            });
        }
        
        // Listen to Back/Forward button navigation and handle rejectionReasonFormGroup display based on session storage
        // When you navigate using forward/back after changing status but not saving, when you land back on the DA page the
        // status select will say (for example) Rejected but the selected option can be something else. To manage the show/hide
        // accurately for this edge case, we use cache and test for the back/forward navigation.
        const observer = new PerformanceObserver((list) => {
            list.getEntries().forEach((entry) => {
                if (entry.type === "back_forward") {
                    let showTextAreaFormGroup = sessionStorage.getItem(this.sessionVariableName) !== null;
                    this.updateFormGroupVisibility(showTextAreaFormGroup);
                }
            });
        });
        observer.observe({ type: "navigation" });
    }

    updateFormGroupVisibility(showFormGroups) {
        if (showFormGroups) {
            showElement(this.textAreaFormGroup);
            showElement(this.dropdownFormGroup);
        }else {
            hideElement(this.textAreaFormGroup);
            hideElement(this.dropdownFormGroup);
        }
    }

    initializeDropdown() {
        if (this.dropdown) {
            this.dropdown.addEventListener("change", () => {
                let reason = this.dropdown.value;
                if (this.initialDropdownValue !== this.dropdown.value || this.initialEmailValue !== this.textarea.value) {
                    let searchParams = new URLSearchParams(
                        {
                            "reason": reason,
                            "domain_request_id": this.domainRequestId,
                        }
                    );
                    // Replace the email content
                    fetch(`${this.apiUrl}?${searchParams.toString()}`)
                    .then(response => {
                        return response.json().then(data => data);
                    })
                    .then(data => {
                        if (data.error) {
                            console.error("Error in AJAX call: " + data.error);
                        }else {
                            this.textarea.value = data.email;
                        }
                        this.updateUserInterface(reason);
                    })
                    .catch(error => {
                        console.error(this.apiErrorMessage, error)
                    });
                }
            });
        }
    }

    initializeModalConfirm() {
        // When the modal confirm button is present, add a listener
        if (this.modalConfirm) {
            this.modalConfirm.addEventListener("click", () => {
                this.textarea.removeAttribute('readonly');
                this.textarea.focus();
                hideElement(this.directEditButton);
                hideElement(this.modalTrigger);  
            });
        }
    }

    initializeDirectEditButton() {
        // When the direct edit button is present, add a listener
        if (this.directEditButton) {
            this.directEditButton.addEventListener("click", () => {
                this.textarea.removeAttribute('readonly');
                this.textarea.focus();
                hideElement(this.directEditButton);
                hideElement(this.modalTrigger);  
            });
        }
    }

    isEmailAlreadySent() {
        return this.lastSentEmailContent.value.replace(/\s+/g, '') === this.textarea.value.replace(/\s+/g, '');
    }

    updateUserInterface(reason, excluded_reasons=["other"]) {
        if (!reason) {
            // No reason selected, we will set the label to "Email", show the "Make a selection" placeholder, hide the trigger, textarea, hide the help text
            this.showPlaceholderNoReason();
        } else if (excluded_reasons.includes(reason)) {
            // 'Other' selected, we will set the label to "Email", show the "No email will be sent" placeholder, hide the trigger, textarea, hide the help text
            this.showPlaceholderOtherReason();
        } else {
            this.showReadonlyTextarea();
        }
    }

    // Helper function that makes overriding the readonly textarea easy
    showReadonlyTextarea() {
        if (this.textarea && this.textareaPlaceholder) {
            // A triggering selection is selected, all hands on board:
            this.textarea.setAttribute('readonly', true);
            showElement(this.textarea);
            hideElement(this.textareaPlaceholder);

                if (this.isEmailAlreadySentConst) {
                    hideElement(this.directEditButton);
                    showElement(this.modalTrigger);
                } else {
                    showElement(this.directEditButton);
                    hideElement(this.modalTrigger);
            }

            if (this.isEmailAlreadySent()) {
                this.formLabel.innerHTML = "Email sent to requester:";
            } else {
                this.formLabel.innerHTML = "Email:";
            }
        }
    }

    // Helper function that makes overriding the placeholder reason easy
    showPlaceholderNoReason() {
        this.showPlaceholder("Email:", "Select a reason to see email");
    }

    // Helper function that makes overriding the placeholder reason easy
    showPlaceholderOtherReason() {
        this.showPlaceholder("Email:", "No email will be sent");
    }

    showPlaceholder(formLabelText, placeholderText) {
        this.formLabel.innerHTML = formLabelText;
        this.textareaPlaceholder.innerHTML = placeholderText;
            showElement(this.textareaPlaceholder);
            hideElement(this.directEditButton);
            hideElement(this.modalTrigger);
            hideElement(this.textarea);
    }
}

class customActionNeededEmail extends CustomizableEmailBase {
    constructor() {
        const emailConfig = {
            dropdown: document.getElementById("id_action_needed_reason"),
            textarea: document.getElementById("id_action_needed_reason_email"),
            lastSentEmailContent: document.getElementById("last-sent-action-needed-email-content"),
            modalConfirm: document.getElementById("action-needed-reason__confirm-edit-email"),
            apiUrl: document.getElementById("get-action-needed-email-for-user-json")?.value || null,
            textAreaFormGroup: document.querySelector('.field-action_needed_reason_email'),
            dropdownFormGroup: document.querySelector('.field-action_needed_reason'),
            statusToCheck: "action needed",
            readonlyStatusToCheck: "Action needed",
            sessionVariableName: "showActionNeededReason",
            apiErrorMessage: "Error when attempting to grab action needed email: "
        }
        super(emailConfig);
    }

    loadActionNeededEmail() {
        // Hide/show the email fields depending on the current status
        this.initializeFormGroups();
        // Setup the textarea, edit button, helper text
        let reason = null;
        if (this.dropdown) {
            reason = this.dropdown.value;
        } else if (this.dropdownFormGroup && this.dropdownFormGroup.querySelector("div.readonly")) {
            if (this.dropdownFormGroup.querySelector("div.readonly").textContent) {
                reason = this.dropdownFormGroup.querySelector("div.readonly").textContent.trim()
            }
        }
        this.updateUserInterface(reason);
        this.initializeDropdown();
        this.initializeModalConfirm();
        this.initializeDirectEditButton();
    }

    // Overrides the placeholder text when no reason is selected
    showPlaceholderNoReason() {
        this.showPlaceholder("Email:", "Select an action needed reason to see email");
    }

    // Overrides the placeholder text when the reason other is selected
    showPlaceholderOtherReason() {
        this.showPlaceholder("Email:", "No email will be sent");
    }
}

/**
 * A function that hooks to the show/hide button underneath action needed reason.
 * This shows the auto generated email on action needed reason.
*/
export function initActionNeededEmail() {
    document.addEventListener('DOMContentLoaded', function() {
        const domainRequestForm = document.getElementById("domainrequest_form");
        if (!domainRequestForm) {
            return;
        }

        // Initialize UI
        const customEmail = new customActionNeededEmail();

        customEmail.loadActionNeededEmail()
    });
}

class customRejectedEmail extends CustomizableEmailBase {
    constructor() {
        const emailConfig = {
            dropdown: document.getElementById("id_rejection_reason"),
            textarea: document.getElementById("id_rejection_reason_email"),
            lastSentEmailContent: document.getElementById("last-sent-rejection-email-content"),
            modalConfirm: document.getElementById("rejection-reason__confirm-edit-email"),
            apiUrl: document.getElementById("get-rejection-email-for-user-json")?.value || null,
            textAreaFormGroup: document.querySelector('.field-rejection_reason'),
            dropdownFormGroup: document.querySelector('.field-rejection_reason_email'),
            statusToCheck: "rejected",
            readonlyStatusToCheck: "Rejected",
            sessionVariableName: "showRejectionReason",
            errorMessage: "Error when attempting to grab rejected email: "
        };
        super(emailConfig);
    }

    loadRejectedEmail() {
        this.initializeFormGroups();
        let reason = null;
        if (this.dropdown) {
            reason = this.dropdown.value;
        } else if (this.dropdownFormGroup && this.dropdownFormGroup.querySelector("div.readonly")) {
            if (this.dropdownFormGroup.querySelector("div.readonly").textContent) {
                reason = this.dropdownFormGroup.querySelector("div.readonly").textContent.trim()
            }
        }
        this.updateUserInterface(reason);
        this.initializeDropdown();
        this.initializeModalConfirm();
        this.initializeDirectEditButton();
    }

    // Overrides the placeholder text when no reason is selected
    showPlaceholderNoReason() {
        this.showPlaceholder("Email:", "Select a rejection reason to see email");
    }

    updateUserInterface(reason, excluded_reasons=[]) {
        super.updateUserInterface(reason, excluded_reasons);
    }
}


/**
 * A function that hooks to the show/hide button underneath rejected reason.
 * This shows the auto generated email on action needed reason.
*/
export function initRejectedEmail() {
    document.addEventListener('DOMContentLoaded', function() {
        const domainRequestForm = document.getElementById("domainrequest_form");
        if (!domainRequestForm) {
            return;
        }

        // Initialize UI
        const customEmail = new customRejectedEmail();
        customEmail.loadRejectedEmail()
    });
}


/**
 * A function that handles the suborganzation and requested suborganization fields and buttons.
 * - Fieldwise: Hooks to the sub_organization, suborganization_city, and suborganization_state_territory fields.
 *   On change, this function checks if any of these fields are not empty: 
 *   sub_organization, suborganization_city, and suborganization_state_territory.
 *   If they aren't, then we show the "clear" button. If they are, then we hide it because we don't need it.
 * 
 * - Buttonwise: Hooks to the #clear-requested-suborganization button.
 *   On click, this will clear the input value of sub_organization, suborganization_city, and suborganization_state_territory.
*/
function handleSuborgFieldsAndButtons() {
    const requestedSuborganizationField = document.getElementById("id_requested_suborganization");
    const suborganizationCity = document.getElementById("id_suborganization_city");
    const suborganizationStateTerritory = document.getElementById("id_suborganization_state_territory");
    const rejectButton = document.querySelector("#clear-requested-suborganization");

    // Ensure that every variable is present before proceeding
    if (!requestedSuborganizationField || !suborganizationCity || !suborganizationStateTerritory || !rejectButton) {
        return;
    }

    function handleRejectButtonVisibility() {
        if (requestedSuborganizationField.value || suborganizationCity.value || suborganizationStateTerritory.value) {
            showElement(rejectButton);
        }else {
            hideElement(rejectButton)
        }
    } 

    function handleRejectButton() {
        // Clear the text fields
        requestedSuborganizationField.value = "";
        suborganizationCity.value = "";
        suborganizationStateTerritory.value = "";
        // Update button visibility after clearing
        handleRejectButtonVisibility();
    }
    rejectButton.addEventListener("click", handleRejectButton)
    requestedSuborganizationField.addEventListener("blur", handleRejectButtonVisibility);
    suborganizationCity.addEventListener("blur", handleRejectButtonVisibility);
    suborganizationStateTerritory.addEventListener("change", handleRejectButtonVisibility);
}

/**
 * A function for dynamic DomainRequest fields
*/
export function initDynamicDomainRequestFields(){
    const domainRequestPage = document.getElementById("domainrequest_form");
    if (domainRequestPage) {
        handlePortfolioSelection();
        handleSuborgFieldsAndButtons();
    }
}

export function initFilterFocusListeners() {
    document.addEventListener("DOMContentLoaded", function() {
        let filters = document.querySelectorAll("#changelist-filter li a"); // Get list of all filter links
        let clickedFilter = false;  // Used to determine if we are truly navigating away or not
    
        // Restore focus from localStorage
        let lastClickedFilterId = localStorage.getItem("admin_filter_focus_id");
        if (lastClickedFilterId) {
            let focusedElement = document.getElementById(lastClickedFilterId);
            if (focusedElement) {
                //Focus the element
                focusedElement.setAttribute("tabindex", "0"); 
                focusedElement.focus({ preventScroll: true });

                // Announce focus change for screen readers
                announceForScreenReaders("Filter refocused on " + focusedElement.textContent);
                localStorage.removeItem("admin_filter_focus_id");
            }
        }

        // Capture clicked filter and store its ID
        filters.forEach(filter => {
            filter.addEventListener("click", function() {
                localStorage.setItem("admin_filter_focus_id", this.id);
                clickedFilter = true; // Mark that a filter was clicked
            });
        });
    });
}