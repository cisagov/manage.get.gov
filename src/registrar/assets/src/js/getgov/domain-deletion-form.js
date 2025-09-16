import { submitForm } from './form-helpers.js';

export function domainDeletionEventListener() {
    /*
    checkbox: the policy acknowledgment checkbox
    modalTrigger: hidden trigger for the modal on the request deletion button
    requestButton: “request deletion” button that opens the modal
    confirmButton: modals "yes, delete" or whatever it is button
    form: the deletion form we'll submit
    */
    const checkbox = document.getElementById("delete-domain-checkbox"); 
    const modalTrigger = document.getElementById("open-delete-domain-modal");
    const requestButton = document.getElementById("request-domain-deletion-button");
    const confirmButton = document.getElementById("domain-deletion-confirm-button");
    const form = document.getElementById("submit-domain-deletion-form");

    // defensive -- if elements dont exist, stop execution
    if (!checkbox || !modalTrigger || !requestButton || !confirmButton || !form) return;

    // Click "Request deletion" button
    requestButton.addEventListener("click", (e) => {
        // e.preventDefault();

        if (!checkbox.checked) {
            // Checkbox not checked -> submit form to default action (domain-delete)
            console.log("!! Checkbox not checked")
            form.submit();
            // submitForm("submit-domain-deletion-form")
            return;
        } 

        // Checkbox checked -> manually "click" the hidden link/modaltrigger to let USWDS open modal
        // e.preventDefault();
        console.log("!! Checkbox checked")
        modalTrigger.click();
    });

    // Confirm deletion inside modal that opens after checkbox checked + "request deletion" button clicked
    confirmButton.addEventListener("click", (e) => {
        console.log("!! In confirm button for the modal")
        // e.preventDefault();
        console.log("!! Submitting form to:", form.action);
        form.submit();
    });
 }