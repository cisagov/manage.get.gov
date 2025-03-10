import { submitForm } from './form-helpers.js';

export function initDomainDSData() {
    document.addEventListener('DOMContentLoaded', function() {
        let domain_dsdata_page = document.getElementById("domain-dsdata");
        if (domain_dsdata_page) {
            const override_button = document.getElementById("disable-override-click-button");
            const cancel_button = document.getElementById("btn-cancel-click-button");
            const cancel_close_button = document.getElementById("btn-cancel-click-close-button");
            if (override_button) {
                override_button.addEventListener("click", function () {
                    submitForm("disable-override-click-form");
                });
            }
            if (cancel_button) {
                cancel_button.addEventListener("click", function () {
                    submitForm("btn-cancel-click-form");
                });
            } 
            if (cancel_close_button) {
                cancel_close_button.addEventListener("click", function () {
                    submitForm("btn-cancel-click-form");
                });
            } 
        }
    });
}