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

    // Defensive check -- if elements dont exist, stop execution
    if (!checkbox || !modalTrigger || !requestButton || !confirmButton || !form) return;

    // "Request deletion" button
    requestButton.addEventListener("click", (e) => {

        // Checkbox not checked -> submit form to default action (domain-delete)
        if (!checkbox.checked) {
            console.log("!! Checkbox not checked")
            form.submit();
            return;
        } 

        // Checkbox checked -> manually "click" the hidden link/modaltrigger to let USWDS open modal
        console.log("!! Checkbox checked")
        modalTrigger.click();
    });

    // Clicking "Yes, request deletion" inside modal that opens after checkbox checked + "request deletion" button clicked
    confirmButton.addEventListener("click", (e) => {
        console.log("!! In confirm button for the modal")
        console.log("!! Submitting form to:", form.action);
        form.submit();
    });
 }