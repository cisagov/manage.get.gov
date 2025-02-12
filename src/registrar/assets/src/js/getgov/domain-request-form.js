import { submitForm } from './helpers.js';

export function initDomainRequestForm() {
    document.addEventListener('DOMContentLoaded', function() {
        initCurrentWebsites();
        initReview();
    });
}

function initReview() {
    const button = document.getElementById("domain-request-form-submit-button");
    if (button) {
        button.addEventListener("click", function () {
            submitForm("submit-domain-request-form");
        });
    } 
}

function initCurrentWebsites() {
    //register-form-step
    const addAnotherSiteButton = document.getElementById("add-another-site-button");
    if (addAnotherSiteButton) {
        // Check for focus state in sessionStorage
        const focusTarget = sessionStorage.getItem("lastFocusedElement");
        if (focusTarget) {
            document.querySelector(focusTarget)?.focus();
        }
        // Add form submit handler to store focus state
        const form = document.querySelector("form");
        if (form) {
            form.addEventListener("submit", () => {
                const activeElement = document.activeElement;
                if (activeElement) {
                    sessionStorage.setItem("lastFocusedElement", "#" + activeElement.id);
                }
            });
        }
        // We only want to do this action once, so we clear out the session
        sessionStorage.removeItem("lastFocusedElement");
    }
}