import { hideElement } from './helpers-admin.js';

/** An IIFE for toggling the overflow styles on django-admin__model-description (the show more / show less button) */
export function initDescriptions() {
    function handleShowMoreButton(toggleButton, descriptionDiv){
        // Check the length of the text content in the description div
        if (descriptionDiv.textContent.length < 200) {
            // Hide the toggle button if text content is less than 200 characters
            // This is a little over 160 characters to give us some wiggle room if we
            // change the font size marginally.
            if (toggleButton)
                hideElement(toggleButton);
        } else {
            toggleButton.addEventListener('click', function() {
                toggleShowMoreButton(toggleButton, descriptionDiv, 'dja__model-description--no-overflow');
            });
        }
    }

    function toggleShowMoreButton(toggleButton, descriptionDiv, showMoreClassName){
        // Toggle the class on the description div
        descriptionDiv.classList.toggle(showMoreClassName);

        // Change the button text based on the presence of the class
        if (descriptionDiv.classList.contains(showMoreClassName)) {
            toggleButton.textContent = 'Show less';
        } else {    
            toggleButton.textContent = 'Show more';
        }
    }

    let toggleButton = document.getElementById('dja-show-more-model-description');
    let descriptionDiv = document.querySelector('.dja__model-description');
    if (toggleButton && descriptionDiv) {
        handleShowMoreButton(toggleButton, descriptionDiv);
    }
}
