import { hideElement, showElement } from './helpers-admin.js';

/** Update tribe details and connect the fed/state dropdown to Django's related widgets. */
function setupAdminTribeSelection(form, tribeDropdown) {
    const recognitionRow = form.querySelector('.field-tribe_recognition');
    const organizationRow = form.querySelector('.field-organization_name');
    if (!recognitionRow || !organizationRow) {
        return;
    }

    const recognitionLabel = recognitionRow.querySelector('label');
    const recognitionDisplay = recognitionRow.querySelector('.readonly');
    const organizationInput = organizationRow.querySelector('input');
    const organizationDisplay = organizationRow.querySelector('.readonly');
    const organizationTypeDropdown = form.querySelector('#id_organization_type');
    const relatedWidgets = form.querySelectorAll('.tribe-related-widget');

    let originalOrganizationName = '';
    if (organizationInput) {
        originalOrganizationName = organizationInput.value;
    } else if (organizationDisplay) {
        originalOrganizationName = organizationDisplay.textContent.trim();
    }
    const hadSavedTribe = tribeDropdown.dataset.hasSavedTribe === 'true';

    function updateRelatedTribeWidgets(selectedType, selectedId) {
        for (const container of relatedWidgets) {
            const relatedDropdown = container.querySelector('select');
            let relatedTribeId = '';
            if (container.dataset.tribeType === selectedType) {
                relatedTribeId = selectedId;
                showElement(container);
            } else {
                hideElement(container);
            }
            if (relatedDropdown.value !== relatedTribeId) {
                // _get_related_choices() in widgets.py provides all choices for this tribe type.
                // relatedDropdown.value selects an existing option from the list.
                relatedDropdown.value = relatedTribeId;
                // Django listens for this event to update the pencil and view links.
                django.jQuery(relatedDropdown).trigger('change');
            }
        }
    }

    function updateTribeFields() {
        const selectedOption = tribeDropdown.selectedOptions[0];
        let recognitionLabelText = 'Federally recognized tribe:';
        let recognitionValue = '';
        let organizationName = originalOrganizationName;
        let tribeType = '';
        let tribeId = '';

        if (tribeDropdown.value) {
            // Combined choices use a type prefix, such as "federal:12" or "state:34".
            const tribeParts = tribeDropdown.value.split(':', 2);
            tribeType = tribeParts[0];
            tribeId = tribeParts[1];
            if (tribeType === 'state') {
                recognitionLabelText = 'State recognized tribe:';
            }
            // Federal is the default
            recognitionValue = 'Yes';
            // Values are Yes or blank
            organizationName = selectedOption.textContent.trim();
        } else if (hadSavedTribe) {
            // Clear a removed tribe's name
            organizationName = '';
        }
        recognitionLabel.textContent = recognitionLabelText;
        recognitionDisplay.textContent = recognitionValue;

        let isTribalOrganization = true;
        if (organizationTypeDropdown) {
            isTribalOrganization = organizationTypeDropdown.value === 'tribal';
        }
        if (organizationInput) {
            organizationInput.readOnly = isTribalOrganization;
            if (isTribalOrganization) {
                organizationInput.value = organizationName;
            }
        } else if (isTribalOrganization && organizationDisplay) {
            organizationDisplay.textContent = organizationName;
        }

        updateRelatedTribeWidgets(tribeType, tribeId);
    }

    // Populate the fields for saved selections and forms returned with validation errors.
    updateTribeFields();

    tribeDropdown.addEventListener('change', updateTribeFields);
    if (organizationTypeDropdown) {
        organizationTypeDropdown.addEventListener('change', updateTribeFields);
    }

    for (const container of relatedWidgets) {
        const relatedDropdown = container.querySelector('select');
        django.jQuery(relatedDropdown).on('change', function(event) {
            // A popup edit sends the changed option; a dropdown change sends the select.
            let changedOption = event.target;
            if (changedOption.tagName !== 'OPTION') {
                changedOption = relatedDropdown.selectedOptions[0];
            }
            if (!changedOption || !changedOption.value) {
                return;
            }
            const combinedValue = `${container.dataset.tribeType}:${changedOption.value}`;
            const combinedOption = tribeDropdown.querySelector(`option[value="${combinedValue}"]`);
            if (combinedOption && combinedOption.textContent !== changedOption.textContent) {
                combinedOption.textContent = changedOption.textContent;
                updateTribeFields();
            }
        });
    }
}

//Entry point
export function initAdminTribeSelection() {
    document.addEventListener('DOMContentLoaded', function() {
        const form = document.getElementById('domainrequest_form');
        if (!form) {
            return;
        }

        const tribeDropdown = form.querySelector('#id_tribe');
        if (!tribeDropdown) {
            return;
        }

        setupAdminTribeSelection(form, tribeDropdown);
    });
}
