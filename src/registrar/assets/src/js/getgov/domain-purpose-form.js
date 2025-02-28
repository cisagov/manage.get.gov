import { showElement } from './helpers.js';

export const domain_purpose_choice_callbacks = {
    'new': {
        callback: function(value, element) {
            console.log("Callback for new")
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
        },
        element: document.getElementById('domain-purpose-details-container')
    },
    'redirect': {
        callback: function(value, element) {
            console.log("Callback for redirect")
            // show the purpose details container
            showElement(element);
            // change just the text inside the em tag
            const labelElement = element.querySelector('.usa-label em');
            labelElement.innerHTML = 'Explain why a redirect is necessary. ' +
                '<span class="usa-label--required">*</span>';
        },
        element: document.getElementById('domain-purpose-details-container')
    },
    'other': {
        callback: function(value, element) {
            console.log("Callback for other")
            // Show the purpose details container
            showElement(element);
            // change just the text inside the em tag
            const labelElement = element.querySelector('.usa-label em');
            labelElement.innerHTML = 'Describe how this domain will be used. ' +
                '<span class="usa-label--required">*</span>';
        },
        element: document.getElementById('domain-purpose-details-container')
    }
}