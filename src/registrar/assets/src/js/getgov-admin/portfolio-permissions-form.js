import { hideElement, showElement } from './helpers-admin.js';

/**
 * A function for dynamically changing fields on the UserPortfolioPermissions
 * and PortfolioInvitation admin forms
 */
function handlePortfolioPermissionFields(){

    const roleDropdown = document.getElementById("id_role");
    const userField = document.getElementById("id_user");
    const domainPermissionsField = document.querySelector(".field-domain_permissions");
    const domainRequestPermissionsField = document.querySelector(".field-request_permissions");
    const memberPermissionsField = document.querySelector(".field-member_permissions");
    const sendEmailField = document.querySelector(".field-send_email");
    const sendEmailCheckbox = document.getElementById("id_send_email");
    
    /**
     * Updates the visibility of portfolio permissions fields based on the selected role.
     * 
     * This function checks the value of the role dropdown (`roleDropdown`):
     * - If the selected role is "organization_member":
     *     - Shows the domain permissions field (`domainPermissionsField`).
     *     - Shows the domain request permissions field (`domainRequestPermissionsField`).
     *     - Shows the member permissions field (`memberPermissionsField`).
     * - Otherwise:
     *     - Hides all the above fields.
     * 
     * The function ensures that the appropriate fields are dynamically displayed
     * or hidden depending on the role selection in the form.
     */
    function updatePortfolioPermissionsFormVisibility() {
        if (roleDropdown && domainPermissionsField && domainRequestPermissionsField && memberPermissionsField) {
            if (roleDropdown.value === "organization_member") {
                showElement(domainPermissionsField);
                showElement(domainRequestPermissionsField);
                showElement(memberPermissionsField);
            } else {
                hideElement(domainPermissionsField);
                hideElement(domainRequestPermissionsField);
                hideElement(memberPermissionsField);
            }
        }
    }

    function isSelectedUserIdValue(value) {
        const normalizedValue = String(value ?? "");
        return normalizedValue !== "" && Number.isInteger(Number(normalizedValue));
    }

    function updateSendEmailVisibility() {
        if (!sendEmailField || !sendEmailCheckbox) {
            return;
        }

        if (isSelectedUserIdValue(userField?.value)) {
            showElement(sendEmailField);
            sendEmailCheckbox.disabled = false;
        } else {
            hideElement(sendEmailField);
            sendEmailCheckbox.checked = false;
            sendEmailCheckbox.disabled = true;
        }
    }


    /**
     * Sets event listeners for key UI elements.
     */
    function setEventListeners() {
        if (roleDropdown) {
            roleDropdown.addEventListener("change", function() {
                updatePortfolioPermissionsFormVisibility();
            })
        }

        if (userField) {
            // The admin autocomplete updates the underlying field value and fires
            // "change" for both selected users and typed email tags.
            userField.addEventListener("change", function() {
                updateSendEmailVisibility();
            });
        }
    }

    // Run initial setup functions
    updatePortfolioPermissionsFormVisibility();
    updateSendEmailVisibility();
    setEventListeners();
}

export function initDynamicPortfolioPermissionFields() {
    document.addEventListener('DOMContentLoaded', function() {
        let isPortfolioPermissionPage = document.getElementById("userportfoliopermission_form");
        let isPortfolioInvitationPage = document.getElementById("portfolioinvitation_form")
        if (isPortfolioPermissionPage || isPortfolioInvitationPage) {
            handlePortfolioPermissionFields();
        }
    });
}
