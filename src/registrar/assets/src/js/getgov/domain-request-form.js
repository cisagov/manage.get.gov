import { submitForm } from './helpers.js';

export function initDomainRequestForm() {
    document.addEventListener('DOMContentLoaded', function() {
        // These are the request steps in DomainRequestWizard, such as current_websites or review
        initRequestStepCurrentWebsites();
        initRequestStepReview();
    });
}

function initRequestStepReview() {
    const button = document.getElementById("domain-request-form-submit-button");
    if (button) {
        button.addEventListener("click", function () {
            submitForm("submit-domain-request-form");
        });
    } 
}

function initRequestStepCurrentWebsites() {
    //register-form-step
    const addAnotherSiteButton = document.getElementById("submit-domain-request--site-button");
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