import { submitForm } from './form-helpers.js';

export function domainDeletionEventListener() {
    const request_submit_button = document.getElementById("domain-deletion-submit-button")
    if(request_submit_button) {
         request_submit_button.addEventListener("click", function () {
           submitForm("submit-domain-deletion-form");
        });
    } 
}
