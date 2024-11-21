function setupUrbanizationToggle(stateTerritoryField) {
    var urbanizationField = document.getElementById('urbanization-field');
    
    function toggleUrbanizationField() {
        // Checking specifically for Puerto Rico only
        if (stateTerritoryField.value === 'PR') { 
        urbanizationField.style.display = 'block';
        } else {
        urbanizationField.style.display = 'none';
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
