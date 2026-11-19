import { setUpUserInvitationFields } from "./user-invitation-form.js";

/**
 * Admin behavior for UserDomainRole form.
 * Shared invitation behavior lives in user-invitation-form.js.
 */

export function initDomainRoleFields() {
    document.addEventListener("DOMContentLoaded", function() {
        if (!document.getElementById("userdomainrole_form")) {
            return;
        }

        const userField = document.getElementById("id_user");
        const sendEmailCheckbox = document.getElementById("id_send_email");
        setUpUserInvitationFields(userField, sendEmailCheckbox);
    });
}
