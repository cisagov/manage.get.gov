import { submitForm } from './helpers.js';

export function initDomainDNSSEC() {
    document.addEventListener('DOMContentLoaded', function() {
        let domain_dnssec_page = document.getElementById("domain-dnssec");
        if (domain_dnssec_page) {
            const button = document.getElementById("disable-dnssec-button");
            if (button) {
                button.addEventListener("click", function () {
                    submitForm("disable-dnssec-form");
                });
            }
        }
    });
}