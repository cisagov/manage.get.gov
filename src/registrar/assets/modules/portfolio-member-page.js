import { uswdsInitializeModals } from './helpers-uswds.js';
import { generateKebabHTML } from './table-base.js';

// This is specifically for the Member Profile (Manage Member) Page member/invitation removal
export function initPortfolioMemberPageToggle() {
    document.addEventListener("DOMContentLoaded", () => {
        const wrapperDeleteAction = document.getElementById("wrapper-delete-action")
        if (wrapperDeleteAction) {
            const member_type = wrapperDeleteAction.getAttribute("data-member-type");
            const member_id = wrapperDeleteAction.getAttribute("data-member-id");
            const num_domains = wrapperDeleteAction.getAttribute("data-num-domains");
            const member_name = wrapperDeleteAction.getAttribute("data-member-name");
            const member_email = wrapperDeleteAction.getAttribute("data-member-email"); 
            const member_delete_url = `${member_type}-${member_id}/delete`;
            const unique_id = `${member_type}-${member_id}`;
    
            let cancelInvitationButton = member_type === "invitedmember" ? "Cancel invitation" : "Remove member";
            wrapperDeleteAction.innerHTML = generateKebabHTML('remove-member', unique_id, cancelInvitationButton, `for ${member_name}`);
    
            // This easter egg is only for fixtures that dont have names as we are displaying their emails
            // All prod users will have emails linked to their account
            MembersTable.addMemberModal(num_domains, member_email || "Samwise Gamgee", member_delete_url, unique_id, wrapperDeleteAction);
    
            uswdsInitializeModals();
    
            // Now the DOM and modals are ready, add listeners to the submit buttons
            const modals = document.querySelectorAll('.usa-modal__content');
    
            modals.forEach(modal => {
              const submitButton = modal.querySelector('.usa-modal__submit');
              const closeButton = modal.querySelector('.usa-modal__close');
              submitButton.addEventListener('click', () => {
                closeButton.click();
                let delete_member_form = document.getElementById("member-delete-form");
                if (delete_member_form) {
                  delete_member_form.submit();
                }
              });
            });
        }
    });
}
