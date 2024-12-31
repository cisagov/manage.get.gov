import { submitForm } from './helpers.js';

export function initDomainManagersPage() {
    document.addEventListener('DOMContentLoaded', function() {
        let domain_managers_page = document.getElementById("domain-managers");
        if (domain_managers_page) {
            // Add event listeners for all buttons matching user-delete-button-{NUMBER}
            const deleteButtons = document.querySelectorAll('[id^="user-delete-button-"]'); // Select buttons with ID starting with "user-delete-button-"
            deleteButtons.forEach((button) => {
                const buttonId = button.id; // e.g., "user-delete-button-1"
                const number = buttonId.split('-').pop(); // Extract the NUMBER part
                const formId = `user-delete-form-${number}`; // Generate the corresponding form ID
                
                button.addEventListener("click", function () {
                    submitForm(formId); // Pass the form ID to submitForm
                });
            });
        } 
    });
}