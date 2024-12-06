import { hideElement, showElement } from './helpers.js';

function setupUrbanizationToggle(stateTerritoryField) {
    let urbanizationField = document.getElementById('urbanization-field');
    if (!urbanizationField) {
        console.error("Cannot find expect field: #urbanization-field");
        return;
    }
    
    function toggleUrbanizationField() {
        // Checking specifically for Puerto Rico only
        if (stateTerritoryField.value === 'PR') { 
            showElement(urbanizationField);
        } else {
            hideElement(urbanizationField);
        }
    }
    
    toggleUrbanizationField();
    
    stateTerritoryField.addEventListener('change', toggleUrbanizationField);
}

export function initializeUrbanizationToggle() {
    document.addEventListener('DOMContentLoaded', function() {
        let stateTerritoryField = document.querySelector('select[name="organization_contact-state_territory"]');
    
        if (!stateTerritoryField) {
        return; // Exit if the field not found
        }
    
        setupUrbanizationToggle(stateTerritoryField);
    });
}
