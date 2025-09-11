import { submitForm } from './form-helpers.js';

export function domainDeletionEventListener() {
    const request_submit_button = document.getElementById("domain-deletion-submit-button")
    const checkbox = document.getElementById("delete-domain-checkbox")
    const deletionModal = document.getElementById("toggle-delete-domain")
    const submit_form = document.getElementById("submit-domain-deletion-form")
    if(request_submit_button) {
         request_submit_button.addEventListener("click", function (e) {
           e.preventDefault();
           submitForm("submit-domain-deletion-form");
           if(checkbox.checked){
            console.log(" ARE WE HERE?!")
            deletionModal.toggleModal(undefined, true)
           }
        });
    } 
}
