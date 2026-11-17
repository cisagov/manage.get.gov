import { hideElement, showElement } from './helpers.js';

/**
 * Once either federally or state recognized or both federally and state
 * recognized is checked, we display the tribe list dropdown 
 * We want to pick which list to show:
 * If ONLY State is checked -> show State Tribes
 * If ONLY Federal is checked -> show Federal Tribes
 * If Federal AND State is checked -> show Federal Tribes
 */
function setupTribalGovernmentToggle(federalCheckbox, stateCheckbox) {
    // ids for the domain_request_tribal_government.html file
    let wrapper = document.getElementById('tribe-select-wrapper');
    let federalField = document.getElementById('federal-tribe-field');
    let stateField = document.getElementById('state-tribe-field');

    if (!wrapper || !federalField || !stateField) {
        console.error("Cannot find expected tribe dropdown fields");
        return;
    }

    function toggleTribeFields() {
        if (federalCheckbox.checked) {
            showElement(wrapper);
            showElement(federalField);
            hideElement(stateField);
        } else if (stateCheckbox.checked) {
            showElement(wrapper);
            hideElement(federalField);
            showElement(stateField);
        } else {
            hideElement(wrapper);
            hideElement(federalField);
            hideElement(stateField);
        }
    }

    // Run once so a page loaded with boxes already checked (ie back button,
    // or a form that came back with errors) shows the right list
    toggleTribeFields();

    federalCheckbox.addEventListener('change', toggleTribeFields);
    stateCheckbox.addEventListener('change', toggleTribeFields);
}

export function initializeTribalGovernmentToggle() {
    document.addEventListener('DOMContentLoaded', function() {
        let federalCheckbox = document.querySelector(
            'input[name="tribal_government-federally_recognized_tribe"]'
        );
        let stateCheckbox = document.querySelector(
            'input[name="tribal_government-state_recognized_tribe"]'
        );

        // NOT on the tribal government step
        if (!federalCheckbox || !stateCheckbox) {
            return; 
        }

        setupTribalGovernmentToggle(federalCheckbox, stateCheckbox);
    });
}