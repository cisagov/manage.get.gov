import { submitForm } from './helpers.js';

export function initDomainRequestForm() {
    document.addEventListener('DOMContentLoaded', function() {
        const button = document.getElementById("domain-request-form-submit-button");
        if (button) {
            button.addEventListener("click", function () {
                submitForm("submit-domain-request-form");
            });
        } 
    });
}