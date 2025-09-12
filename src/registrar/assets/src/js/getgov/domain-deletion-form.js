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

import { submitForm } from './form-helpers.js';

export function domainDeletionEventListener() {
    const checkbox = document.getElementById("delete-domain-checkbox"); 
    const modal = document.getElementById("toggle-delete-domain");
    const requestButton = document.getElementById("request-domain-deletion-button");
    const confirmButton = document.getElementById("domain-deletion-confirm-button");

    // Stops the JS from crashing if any of the properties are null
    if (!checkbox || !modal || !requestButton || !confirmButton) return;

    /*
    1. Unchecked checkbox -> Click "request delete" button -> submit directly, no modal, display error
    2. Checked checkbox -> Click "request delete" button -> modal opens
    2a. Once modal is open, if user clicks confirm, submit and close modal automatically.
    https://github.com/uswds/uswds/blob/9999d08fe6c8e7f0aaa3f24b86ba37b281c25b54/packages/usa-modal/src/index.js#L26
    */
    // REQUEST DELETION BUTTON
    requestButton.addEventListener("click", (e) => {

    if (!checkbox.checked) {
      e.preventDefault();
      console.log("Checkbox not checked --> submit form for error");
      submitForm("submit-domain-deletion-form");
    } else {
      e.preventDefault();
      console.log("+ Checkbox checked --> show modal");
      modal.classList.remove("is-hidden"); // Shows modal after submit
      modal.setAttribute("aria-hidden", "false");
    }
    });

    // CONFIRM DELETION BUTTON INSIDE MODAL
    confirmButton.addEventListener("click", (e) => {
        e.preventDefault();
        console.log("Confirm deletion clicked --> submit form");
        submitForm("submit-domain-deletion-form");
        modal.classList.add("is-hidden"); // Hides modal after submit
        modal.setAttribute("aria-hidden", "true");
    });
}