import { hideElement, showElement } from './helpers-admin.js';

/**
 * A function for dynamically changing fields on the UserPortfolioPermissions
 * and PortfolioInvitation admin forms
 */
function handlePortfolioPermissionFields(){

    const roleDropdown = document.getElementById("id_role");
    const domainPermissionsField = document.querySelector(".field-domain_permissions");
    const domainRequestPermissionsField = document.querySelector(".field-request_permissions");
    const memberPermissionsField = document.querySelector(".field-member_permissions");
    
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


    /**
     * Sets event listeners for key UI elements.
     */
    function setEventListeners() {
        if (roleDropdown) {
            roleDropdown.addEventListener("change", function() {
                updatePortfolioPermissionsFormVisibility();
            })
        }
    }

    // Run initial setup functions
    updatePortfolioPermissionsFormVisibility();
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
