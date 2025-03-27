import { showElement } from './helpers.js';

// Flag to track if we're in the initial page load
let isInitialLoad = true;

export const domain_purpose_choice_callbacks = {
    'new': {
        callback: function(value, element, event) {
            // Only clear errors if this is a user-initiated event (not initial page load)
            if (!isInitialLoad) {
                clearErrors(element);
            }

            //show the purpose details container
            showElement(element);
            // change just the text inside the em tag
            const labelElement = element.querySelector('.usa-label em');
            labelElement.innerHTML = 'Explain why a new domain is required and why a ' +
                'subdomain of an existing domain doesn\'t meet your needs.' +
                '<br><br>' + // Adding double line break for spacing
                'Include any data that supports a clear public benefit or ' +
                'evidence user need for this new domain. ' +
                '<span class="usa-label--required">*</span>';
                
            // Mark that we're no longer in initial load
            isInitialLoad = false;
        },
        element: document.getElementById('purpose-details-container')
    },
    'redirect': {
        callback: function(value, element, event) {
            // Only clear errors if this is a user-initiated event (not initial page load)
            if (!isInitialLoad) {
                clearErrors(element);
            }

            // show the purpose details container
            showElement(element);
            // change just the text inside the em tag
            const labelElement = element.querySelector('.usa-label em');
            labelElement.innerHTML = 'Explain why a redirect is necessary. ' +
                '<span class="usa-label--required">*</span>';
                
            // Mark that we're no longer in initial load
            isInitialLoad = false;
        },
        element: document.getElementById('purpose-details-container')
    },
    'other': {
        callback: function(value, element, event) {
            // Only clear errors if this is a user-initiated event (not initial page load)
            if (!isInitialLoad) {
                clearErrors(element);
            }

            // Show the purpose details container
            showElement(element);
            // change just the text inside the em tag
            const labelElement = element.querySelector('.usa-label em');
            labelElement.innerHTML = 'Describe how this domain will be used. ' +
                '<span class="usa-label--required">*</span>';
                
            // Mark that we're no longer in initial load
            isInitialLoad = false;
        },
        element: document.getElementById('purpose-details-container')
    }
}

// Function to check if errors are currently displayed
function checkForErrors(element) {
    const errorMessage = element.querySelector('#id_purpose-purpose__error-message');
    const formGroup = element.querySelector('.usa-form-group.usa-form-group--error');
    
    // If either errors exist, set the flag to true
    if (errorMessage || formGroup) {
        errorsHaveBeenDisplayed = true;
    }
    
    return errorsHaveBeenDisplayed;
}

// Helper function to clear error messages in a textarea
function clearErrors(element) {
    // Find the error message div
    const errorMessage = element.querySelector('#id_purpose-purpose__error-message');
    if (errorMessage) {
        errorMessage.remove();
    }
    
    // Find the form group and remove error class
    const formGroup = element.querySelector('.usa-form-group');
    if (formGroup) {
        formGroup.classList.remove('usa-form-group--error');
    }
    
    // Find the textarea and remove error class
    const textarea = element.querySelector('#id_purpose-purpose');
    if (textarea) {
        textarea.classList.remove('usa-input--error');
        
        // Also update aria attributes
        textarea.setAttribute('aria-invalid', 'false');
        
        // Remove error message from aria-describedby
        const describedBy = textarea.getAttribute('aria-describedby');
        if (describedBy) {
            const newDescribedBy = describedBy.replace('id_purpose-purpose__error-message', '').trim();
            textarea.setAttribute('aria-describedby', newDescribedBy);
        }
    }
    
    // Find the label and remove error class
    const label = element.querySelector('label');
    if (label) {
        label.classList.remove('usa-label--error');
    }
}