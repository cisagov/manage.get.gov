import { hideElement, showElement } from './helpers.js';

// <<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>>
// Helper functions.

/** Hookup listeners for yes/no togglers for form fields 
 * Parameters:
 *  - radioButtonName:  The "name=" value for the radio buttons being used as togglers
 *  - elementIdToShowIfYes: The Id of the element (eg. a div) to show if selected value of the given
 * radio button is true (hides this element if false)
 *  - elementIdToShowIfNo: The Id of the element (eg. a div) to show if selected value of the given
 * radio button is false (hides this element if true)
 * **/
export function hookupYesNoListener(radioButtonName, elementIdToShowIfYes, elementIdToShowIfNo) {
    hookupRadioTogglerListener(radioButtonName, {
        'True': elementIdToShowIfYes,
        'False': elementIdToShowIfNo
    });
}
  
/** 
 * Hookup listeners for radio togglers in form fields.
 * 
 * Parameters:
 *  - radioButtonName: The "name=" value for the radio buttons being used as togglers
 *  - valueToElementMap: An object where keys are the values of the radio buttons, 
 *    and values are the corresponding DOM element IDs to show. All other elements will be hidden.
 * 
 * Usage Example:
 * Assuming you have radio buttons with values 'option1', 'option2', and 'option3',
 * and corresponding DOM IDs 'section1', 'section2', 'section3'.
 * 
 * HookupValueBasedListener('exampleRadioGroup', {
 *      'option1': 'section1',
 *      'option2': 'section2',
 *      'option3': 'section3'
 *    });
 **/
export function hookupRadioTogglerListener(radioButtonName, valueToElementMap) {
    // Get the radio buttons
    let radioButtons = document.querySelectorAll(`input[name="${radioButtonName}"]`);
    
    // Extract the list of all element IDs from the valueToElementMap
    let allElementIds = Object.values(valueToElementMap);

    function handleRadioButtonChange() {
        // Find the checked radio button
        let radioButtonChecked = document.querySelector(`input[name="${radioButtonName}"]:checked`);
        let selectedValue = radioButtonChecked ? radioButtonChecked.value : null;
    
        // Hide all elements by default
        allElementIds.forEach(function (elementId) {
            let element = document.getElementById(elementId);
            if (element) {
                hideElement(element);
            }
        });
    
        // Show the relevant element for the selected value
        if (selectedValue && valueToElementMap[selectedValue]) {
            let elementToShow = document.getElementById(valueToElementMap[selectedValue]);
            if (elementToShow) {
            showElement(elementToShow);
            }
        }
    }

    if (radioButtons && radioButtons.length) {
        // Add event listener to each radio button
        radioButtons.forEach(function (radioButton) {
            radioButton.addEventListener('change', handleRadioButtonChange);
        });
    
        // Initialize by checking the current state
        handleRadioButtonChange();
    }
}
