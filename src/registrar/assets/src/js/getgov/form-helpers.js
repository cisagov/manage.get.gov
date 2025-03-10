/**
 * Helper function to submit a form
 * @param {} form_id - the id of the form to be submitted
 */
export function submitForm(form_id) {
    let form = document.getElementById(form_id);
    if (form) {
        form.submit();
    } else {
        console.error("Form '" + form_id + "' not found.");
    }
}


/**
 * Removes all error-related classes and messages from the specified DOM element.
 * This method cleans up validation errors by removing error highlighting from input fields, 
 * labels, and form groups, as well as deleting error message elements.
 * @param {HTMLElement} domElement - The parent element within which errors should be cleared.
 */
export function removeErrorsFromElement(domElement) {
    // Remove the 'usa-form-group--error' class from all div elements
    domElement.querySelectorAll("div.usa-form-group--error").forEach(div => {
        div.classList.remove("usa-form-group--error");
    });

    // Remove the 'usa-label--error' class from all label elements
    domElement.querySelectorAll("label.usa-label--error").forEach(label => {
        label.classList.remove("usa-label--error");
    });

    // Remove all error message divs whose ID ends with '__error-message'
    domElement.querySelectorAll("div[id$='__error-message']").forEach(errorDiv => {
        errorDiv.remove();
    });

    // Remove the 'usa-input--error' class from all input elements
    domElement.querySelectorAll("input.usa-input--error").forEach(input => {
        input.classList.remove("usa-input--error");
    });

    // Remove the 'usa-input--error' class from all select elements
    domElement.querySelectorAll("select.usa-input--error").forEach(select => {
        select.classList.remove("usa-input--error");
    });
}

/**
 * Removes all form-level error messages displayed in the UI.
 * The form error messages are contained within div elements with the ID 'form-errors'.
 * Since multiple elements with the same ID may exist (even though not syntactically correct), 
 * this function removes them iteratively.
 */
export function removeFormErrors() {
    let formErrorDiv = document.getElementById("form-errors");

    // Recursively remove all instances of form error divs
    while (formErrorDiv) {
        formErrorDiv.remove();
        formErrorDiv = document.getElementById("form-errors");
    }
}