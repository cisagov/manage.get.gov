import { submitForm } from './form-helpers.js';

export function initOrganizationsNavDropdown() {
    document.addEventListener('DOMContentLoaded', function() {
        let organizationsMenu = document.getElementById("organizations-menu");
        if (organizationsMenu) {
            // Add event listeners for all links matching set-session-portfolio-link-{NUMBER}
            const organizationMenuLinks = document.querySelectorAll('[id^="set-session-portfolio-link-"]'); // Select buttons with ID starting with "set-session-portfolio-link-"
            organizationMenuLinks.forEach((link) => {
                const linkId = link.id; // e.g., "set-session-portfolio-link-1"
                const number = linkId.split('-').pop(); // Extract the NUMBER part
                const formId = `set-session-portfolio-form-${number}`; // Generate the corresponding form ID

                link.addEventListener("click", function () {
                    submitForm(formId); // Pass the form ID to submitForm
                });
            });
        }
    });
}