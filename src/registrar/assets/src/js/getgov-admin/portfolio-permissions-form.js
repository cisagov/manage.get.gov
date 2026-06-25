import { hideElement, showElement } from './helpers-admin.js';

function isSelectedUserIdValue(value) {
    const normalizedValue = String(value ?? "");
    return normalizedValue !== "" && Number.isInteger(Number(normalizedValue));
}

function setUpSendEmailAvailability(userField, sendEmailCheckbox) {
    function updateSendEmailAvailability() {
        if (!sendEmailCheckbox) {
            return;
        }

        if (isSelectedUserIdValue(userField?.value)) {
            sendEmailCheckbox.disabled = false;
        } else {
            // Typed emails always send an invitation email, so keep the
            // checkbox checked while disabling it.
            sendEmailCheckbox.checked = true;
            sendEmailCheckbox.disabled = true;
        }
    }

    if (userField && typeof django !== "undefined" && django.jQuery) {
        django.jQuery(userField).on("change select2:select select2:clear", function() {
            updateSendEmailAvailability();
        });
    }

    updateSendEmailAvailability();
}

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
    setUpSendEmailAvailability(userField, sendEmailCheckbox);
    setEventListeners();
}

function handleDomainRoleFields() {
    const userField = document.getElementById("id_user");
    const sendEmailCheckbox = document.getElementById("id_send_email");

    setUpSendEmailAvailability(userField, sendEmailCheckbox);
}

export function initDynamicPortfolioPermissionFields() {
    document.addEventListener('DOMContentLoaded', function() {
        let isPortfolioPermissionPage = document.getElementById("userportfoliopermission_form");
        let isPortfolioInvitationPage = document.getElementById("portfolioinvitation_form");
        let isDomainRolePage = document.getElementById("userdomainrole_form");
        if (isPortfolioPermissionPage || isPortfolioInvitationPage) {
            handlePortfolioPermissionFields();
        }
        if (isDomainRolePage) {
            handleDomainRoleFields();
        }
    });
}
