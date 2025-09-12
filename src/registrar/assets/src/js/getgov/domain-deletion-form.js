// import { submitForm } from './form-helpers.js';

// export function domainDeletionEventListener() {
//     const request_submit_button = document.getElementById("domain-deletion-submit-button")
//     const checkbox = document.getElementById("delete-domain-checkbox")
//     const deletionModal = document.getElementById("toggle-delete-domain")
//     const submit_form = document.getElementById("submit-domain-deletion-form")
//     if(request_submit_button) {
//          request_submit_button.addEventListener("click", function (e) {
//            e.preventDefault();
//            submitForm("submit-domain-deletion-form");
//            if(checkbox.checked){
//             console.log(" ARE WE HERE?!")
//             deletionModal.toggleModal(undefined, true)
//            }
//         });
//     } 
// }

// import { submitForm } from './form-helpers.js';

// export function domainDeletionEventListener() {
//   const checkbox = document.getElementById("delete-domain-checkbox"); 
//   const modal = document.getElementById("toggle-delete-domain");
//   const requestButton = document.getElementById("request-domain-deletion-button");
//   const confirmButton = document.getElementById("domain-deletion-confirm-button");

//   // Stops the JS from crashing if any of the properties are null
//   if (!checkbox || !modal || !requestButton || !confirmButton) return;

//   /*
//   1. Unchecked checkbox -> Click "request delete" button -> submit directly, no modal, display error
//   2. Checked checkbox -> Click "request delete" button -> modal opens via USWDS which isn't working
//   because data-open-modal is not working as it should be intended and we're forcing function here with modal to do so.
//   2a. Once modal is open, if user clicks confirm, submit and close modal automatically.
//   FYI the modal stuff is replicating what USWDS's data-open-modal should do
//    */
//   // REQUEST DELETION BUTTON
//   requestButton.addEventListener("click", (e) => {
//     if (!checkbox.checked) {
//       e.preventDefault();
//       console.log("Checkbox not checked --> submit form for error");
//       submitForm("submit-domain-deletion-form");
//     } else {
//       e.preventDefault();
//       console.log("Checkbox checked --> show modal");
//       modal.classList.remove("is-hidden"); // Shows the modal after submit
//       modal.setAttribute("aria-hidden", "false");
//     }
//   });

//   // CONFIRM DELETION BUTTON INSIDE MODAL
//   confirmButton.addEventListener("click", (e) => {
//     e.preventDefault();
//     console.log("Confirm deletion clicked --> submit form");
//     submitForm("submit-domain-deletion-form");
//     modal.classList.add("is-hidden"); // Hides modal after submit
//     modal.setAttribute("aria-hidden", "true");
//   });
// }

import { submitForm } from './form-helpers.js';

export function domainDeletionEventListener() {
    const checkbox = document.getElementById("delete-domain-checkbox");
    const requestButton = document.getElementById("request-domain-deletion-button");
    const confirmButton = document.getElementById("domain-deletion-confirm-button");
    const modal = document.getElementById("toggle-delete-domain");


  // Stop if any essential elements are missing
  if (!checkbox || !requestButton || !confirmButton) return;

  // --- Request deletion button ---
  requestButton.addEventListener("click", (e) => {
    if (!checkbox.checked) {
        // Checkbox not checked -> submit form/get error
        e.preventDefault();
        // Prevent modal from displaying from aria-controls 
        console.log("Checkbox not checked -> submit form for error");
        submitForm("submit-domain-deletion-form");
    } else {
        // modal.setAttribute('aria-hidden', 'false');
        //Otherwise aria-controls opens the modal
        modal.setAttribute('aria-controls', 'toggle-delete-domain')
        console.log("~ IN ELSE: and that the modal should open right")
    }
  });

  // --- Confirm deletion button inside modal ---
  confirmButton.addEventListener("click", (e) => {
    e.preventDefault();
    console.log("Confirm deletion clicked → submit form");

    // Submit the form
    submitForm("submit-domain-deletion-form");

  });
}
