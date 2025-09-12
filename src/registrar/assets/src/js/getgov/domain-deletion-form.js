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
//     const checkbox = document.getElementById("delete-domain-checkbox"); 
//     const modal = document.getElementById("toggle-delete-domain");
//     const requestButton = document.getElementById("request-domain-deletion-button");
//     const confirmButton = document.getElementById("domain-deletion-confirm-button");

//     // Stops the JS from crashing if any of the properties are null
//     if (!checkbox || !modal || !requestButton || !confirmButton) return;

//     /*
//     1. Unchecked checkbox -> Click "request delete" button -> submit directly, no modal, display error
//     2. Checked checkbox -> Click "request delete" button -> modal opens
//     2a. Once modal is open, if user clicks confirm, submit and close modal automatically.
//     https://github.com/uswds/uswds/blob/9999d08fe6c8e7f0aaa3f24b86ba37b281c25b54/packages/usa-modal/src/index.js#L26
//     */
//     // REQUEST DELETION BUTTON
//     requestButton.addEventListener("click", (e) => {

//     if (!checkbox.checked) {
//       e.preventDefault();
//       console.log("Checkbox not checked --> submit form for error");
//       submitForm("submit-domain-deletion-form");
//     } else {
//       e.preventDefault();
//       console.log("+ Checkbox checked --> show modal");
//       modal.classList.remove("is-hidden"); // Shows modal after submit
//       modal.setAttribute("aria-hidden", "false");
//     }
//     });

//     // CONFIRM DELETION BUTTON INSIDE MODAL
//     confirmButton.addEventListener("click", (e) => {
//         e.preventDefault();
//         console.log("!! !Confirm deletion clicked --> submit form");
//         submitForm("submit-domain-deletion-form");
//         modal.classList.add("is-hidden"); // Hides modal after submit
//         modal.setAttribute("aria-hidden", "true");
//     });
// }

// import { submitForm } from './form-helpers.js';

// export function domainDeletionEventListener() {
//   const checkbox = document.getElementById("delete-domain-checkbox"); 
//   const modal = document.getElementById("toggle-delete-domain");
//   const requestButton = document.getElementById("request-domain-deletion-button");
//   const confirmButton = document.getElementById("domain-deletion-confirm-button");
//   const form = document.getElementById("submit-domain-deletion-form");

//   if (!checkbox || !modal || !requestButton || !confirmButton || !form) return;

//     // Click "Request deletion" button
//     requestButton.addEventListener("click", (e) => {
//         e.preventDefault();

//         if (!checkbox.checked) {
//             // Checkbox not checked -> submit form to default action (domain-delete)
//             submitForm("submit-domain-deletion-form");
//         } else {
//             // Checkbox checked -> show modal
//             modal.classList.remove("is-hidden");
//             modal.setAttribute("aria-hidden", "false");
//         }
//     });

//     // Click "Confirm deletion" inside modal
//     confirmButton.addEventListener("click", (e) => {
//         e.preventDefault();

//         // Use the URL from the data attribute on the modal confirm button
//         const domainAction = confirmButton.dataset.domainUrl;
//         form.action = domainAction;

//         // Submit form using your helper
//         submitForm("submit-domain-deletion-form");

//         // Hide modal
//         modal.classList.add("is-hidden");
//         modal.setAttribute("aria-hidden", "true");
//     });

//     // Optional: close modal when clicking outside or on a close button
//     modal.addEventListener("click", (e) => {
//         if (e.target.classList.contains("usa-modal__close") || e.target.dataset.closeModal !== undefined) {
//             console.log("Modal close clicked -> hiding modal");
//             modal.classList.add("is-hidden");
//             modal.setAttribute("aria-hidden", "true");
//         }
//     });
// }


import { submitForm } from './form-helpers.js';

export function domainDeletionEventListener() {
    /*
    checkbox: the policy acknowledgment checkbox
    modal: the modal container element
    requestButton: “request deletion” button that opens the modal
    confirmButton: modals "yes, delete" or whatever it is button
    form: the deletion form we'll submit
    */
    const checkbox = document.getElementById("delete-domain-checkbox"); 
    const modal = document.getElementById("toggle-delete-domain");
    const requestButton = document.getElementById("request-domain-deletion-button");
    const confirmButton = document.getElementById("domain-deletion-confirm-button");
    const form = document.getElementById("submit-domain-deletion-form");

    // defensive, elements dont exist, stop execution
    if (!checkbox || !modal || !requestButton || !confirmButton || !form) return;

    // its like a "placeholder", holds the focus for when the modal closes for accessibility reasons
    let lastFocusedElement = null;

    /*
    1. save the current focused element
    2. make sure modal is visible + screen reader can access modal content
    3. remove the inert so tha the modal elements can be focused and interacted with
    4. if all is good move keyboard focus to confirmbutton for accessilbity reasons
    */
    const showModal = () => {
        lastFocusedElement = document.activeElement;
        modal.classList.remove("is-hidden");
        modal.setAttribute("aria-hidden", "false");

        // Make background inert
        modal.inert = false;

        // Move focus to confirm button
        confirmButton.focus();
    };

    /*
    1. hide modal visually, and hides the modal content for accessibilty stuff so they cant read it
    2. inert being true prevents focus on the modal 
    3. return focus element to the last element that it was on before modal was opened
    */
    const hideModal = () => {
        modal.classList.add("is-hidden");
        modal.setAttribute("aria-hidden", "true");

        // Make modal content inert to prevent focus
        modal.inert = true;

        if (lastFocusedElement) lastFocusedElement.focus();
    };

    /*
    REQUEST DELETION
    1. checkbox NOT checked -> submit form to the domain-dete url
    2. checkbox IS checked -> show the modal
    */
    requestButton.addEventListener("click", (e) => {
        e.preventDefault();

        if (!checkbox.checked) {
            console.log("!!!Request deletion -> checkbox NOT checked, submit to domain-delete url");
            submitForm("submit-domain-deletion-form");
        } else {
            console.log("!!!Request deletion -> checkbox IS checked, showing modal");
            showModal();
        }
    });

    /*
    CONFIRM DELETION
    bc when we want to submit on the modal we want it to go back to domain overview
    1. grab url (we have this set up in the HTML)
    2. form will submit to the right page with form.action
    3. hide modal and restore focus to the element it was at before modal
    */
    confirmButton.addEventListener("click", (e) => {
        e.preventDefault();

        const domainAction = confirmButton.dataset.domainUrl;
        console.log(`Modal confirm -> submitting to: ${domainAction}`);
        form.action = domainAction;
        submitForm("submit-domain-deletion-form");

        hideModal();
    });

    /*
    trigger hide modal with 
    usa-modal__close which is x button, and data-close-modal which is cancel button
    */
    modal.addEventListener("click", (e) => {
        if (e.target.classList.contains("usa-modal__close") || e.target.dataset.closeModal !== undefined) {
            console.log("!!!Modal close clicked -> hiding modal");
            hideModal();
        }
    });

    // hide modal so users cant tab to it for accessibility reasons
    modal.inert = true;
}
