import { submitForm } from './form-helpers.js';

export function domainDeletionEventListener() {
    const request_submit_button = document.getElementById("domain-deletion-submit-button")
    const checkbox = document.getElementById("delete-domain-checkbox")

    if(request_submit_button) {
         request_submit_button.addEventListener("click", function (e) {
           if(!checkbox.checked){
            submitForm("submit-domain-deletion-form");
           }
           else{
              request_submit_button.setAttribute('href','#toggle-delete-domain')       
              request_submit_button.setAttribute('aria-controls', "toggle-delete-domain")
              request_submit_button.click()
           }
        });
    } 
}
