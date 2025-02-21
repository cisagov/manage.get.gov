import { uswdsInitializeModals } from './helpers-uswds.js';
import { getCsrfToken } from './helpers.js';
import { generateKebabHTML } from './table-base.js';
import { MembersTable } from './table-members.js';
import { hookupRadioTogglerListener } from './radios.js';

// This is specifically for the Member Profile (Manage Member) Page member/invitation removal
export function initPortfolioNewMemberPageToggle() {
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
            wrapperDeleteAction.innerHTML = generateKebabHTML('remove-member', unique_id, cancelInvitationButton, `More Options for ${member_name}`);
    
            // This easter egg is only for fixtures that dont have names as we are displaying their emails
            // All prod users will have emails linked to their account
            MembersTable.addMemberDeleteModal(num_domains, member_email || member_name || "Samwise Gamgee", member_delete_url, unique_id, wrapperDeleteAction);
    
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


/**
 * Hooks up specialized listeners for handling form validation and modals
 * on the Add New Member page.
 */
export function initAddNewMemberPageListeners() {
  let add_member_form = document.getElementById("add_member_form");
  if (!add_member_form){
     return;
  }
  document.getElementById("confirm_new_member_submit").addEventListener("click", function() {
    // Upon confirmation, submit the form
    document.getElementById("add_member_form").submit();
  });

  document.getElementById("add_member_form").addEventListener("submit", function(event) {
    event.preventDefault(); // Prevents the form from submitting
    const form = document.getElementById("add_member_form")
    const formData = new FormData(form);

    // Check if the form is valid
    // If the form is valid, open the confirmation modal
    // If the form is invalid, submit it to trigger error 
    fetch(form.action, {
        method: "POST",
        body: formData,
        headers: {
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": getCsrfToken()
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.is_valid) {
            // If the form is valid, show the confirmation modal before submitting
            openAddMemberConfirmationModal();
        } else {
            // If the form is not valid, trigger error messages by firing a submit event
            form.submit();
        }
    });
  });

  /*
    Populates contents of the "Add Member" confirmation modal
  */
  function populatePermissionDetails(permission_details_div_id) {
    const permissionDetailsContainer = document.getElementById("permission_details");
    permissionDetailsContainer.innerHTML = ""; // Clear previous content

    if (permission_details_div_id == 'member-basic-permissions') {
      // for basic users, display values are based on selections in the form
      // Get all permission sections (divs with h3 and radio inputs)
      const permissionSections = document.querySelectorAll(`#${permission_details_div_id} > h3`);

      permissionSections.forEach(section => {
        // Find the <h3> element text
        const sectionTitle = section.textContent;

        // Find the associated radio buttons container (next fieldset)
        const fieldset = section.nextElementSibling;

        if (fieldset && fieldset.tagName.toLowerCase() === 'fieldset') {
          // Get the selected radio button within this fieldset
          const selectedRadio = fieldset.querySelector('input[type="radio"]:checked');

          // If a radio button is selected, get its label text
          let selectedPermission = "No permission selected";
          if (selectedRadio) {
            const label = fieldset.querySelector(`label[for="${selectedRadio.id}"]`);
            if (label) {
              // Get only the text node content (excluding subtext in <p>)
              const mainText = Array.from(label.childNodes)
                  .filter(node => node.nodeType === Node.TEXT_NODE)
                  .map(node => node.textContent.trim())
                  .join(""); // Combine and trim whitespace
              selectedPermission = mainText || "No permission selected";
            }
          }
          appendPermissionInContainer(sectionTitle, selectedPermission, permissionDetailsContainer);
        }
      });
    } else {
      // for admin users, the permissions are always the same
      appendPermissionInContainer('Domains', 'Viewer', permissionDetailsContainer);
      appendPermissionInContainer('Domain requests', 'Creator', permissionDetailsContainer);
      appendPermissionInContainer('Members', 'Manager', permissionDetailsContainer);
    }
  }

  function appendPermissionInContainer(sectionTitle, permissionDisplay, permissionContainer) {
    // Create new elements for the content
    const titleElement = document.createElement("h4");
    titleElement.textContent = sectionTitle;
    titleElement.classList.add("text-primary", "margin-bottom-0");

    const permissionElement = document.createElement("p");
    permissionElement.textContent = permissionDisplay;
    permissionElement.classList.add("margin-top-0");

    // Append to the content container
    permissionContainer.appendChild(titleElement);
    permissionContainer.appendChild(permissionElement);
  }

  /*
    Updates and opens the "Add Member" confirmation modal.
  */
  function openAddMemberConfirmationModal() {
      //------- Populate modal details
      // Get email value
      let emailValue = document.getElementById('id_email').value;
      document.getElementById('modalEmail').textContent = emailValue;

      // Get selected radio button for member access level
      let selectedAccess = document.querySelector('input[name="role"]:checked');
      // Map the access level values to user-friendly labels
      const accessLevelMapping = {
        organization_admin: "Admin",
        organization_member: "Basic",
      };
      // Determine the access text based on the selected value
      let accessText = selectedAccess 
        ? accessLevelMapping[selectedAccess.value] || "Unknown access level" 
        : "No access level selected";
      // Update the modal with the appropriate member access level text
      document.getElementById('modalAccessLevel').textContent = accessText;

      // Populate permission details based on access level
      if (selectedAccess && selectedAccess.value === 'organization_admin') {
        populatePermissionDetails('admin');
      } else {
        populatePermissionDetails('member-basic-permissions');
      }

      //------- Show the modal
      let modalTrigger = document.querySelector("#invite_member_trigger");
        if (modalTrigger) {
          modalTrigger.click();
        }
  }

}

// Initalize the radio for the member pages
export function initPortfolioMemberPageRadio() {
  document.addEventListener("DOMContentLoaded", () => {
      let memberForm = document.getElementById("member_form");
      let newMemberForm = document.getElementById("add_member_form")
      if (memberForm || newMemberForm) {
        hookupRadioTogglerListener(
          'role', 
          {
            'organization_admin': '',
            'organization_member': 'member-basic-permissions'
          }
        );
      }
  });
}
