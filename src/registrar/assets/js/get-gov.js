/**
 * @file get-gov.js includes custom code for the .gov registrar.
 *
 * Constants and helper functions are at the top.
 * Event handlers are in the middle.
 * Initialization (run-on-load) stuff goes at the bottom.
 */


var DEFAULT_ERROR = "Please check this field for errors.";

var INFORMATIVE = "info";
var WARNING = "warning";
var ERROR = "error";
var SUCCESS = "success";

// <<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>>
// Helper functions.

/**
 * Hide element
 *
*/
const hideElement = (element) => {
  element.classList.add('display-none');
};

/**
 * Show element
 *
*/
const showElement = (element) => {
  element.classList.remove('display-none');
};

/**
 * Helper function to get the CSRF token from the cookie
 *
*/
function getCsrfToken() {
  return document.querySelector('input[name="csrfmiddlewaretoken"]').value;
}

/**
 * Helper function that scrolls to an element
 * @param {string} attributeName - The string "class" or "id"
 * @param {string} attributeValue - The class or id name
 */
function ScrollToElement(attributeName, attributeValue) {
  let targetEl = null;

  if (attributeName === 'class') {
    targetEl = document.getElementsByClassName(attributeValue)[0];
  } else if (attributeName === 'id') {
    targetEl = document.getElementById(attributeValue);
  } else {
    console.error('Error: unknown attribute name provided.');
    return; // Exit the function if an invalid attributeName is provided
  }

  if (targetEl) {
    const rect = targetEl.getBoundingClientRect();
    const scrollTop = window.scrollY || document.documentElement.scrollTop;
    window.scrollTo({
      top: rect.top + scrollTop,
      behavior: 'smooth' // Optional: for smooth scrolling
    });
  }
}

/** Makes an element invisible. */
function makeHidden(el) {
  el.style.position = "absolute";
  el.style.left = "-100vw";
  // The choice of `visiblity: hidden`
  // over `display: none` is due to
  // UX: the former will allow CSS
  // transitions when the elements appear.
  el.style.visibility = "hidden";
}

/** Makes visible a perviously hidden element. */
function makeVisible(el) {
  el.style.position = "relative";
  el.style.left = "unset";
  el.style.visibility = "visible";
}

/**
 * Creates and adds a modal dialog to the DOM with customizable attributes and content.
 *
 * @param {string} action - The action type or identifier used to create a unique modal ID.
 * @param {string} id - A unique identifier for the modal, appended to the action for uniqueness.
 * @param {string} ariaLabelledby - The ID of the element that labels the modal, for accessibility.
 * @param {string} ariaDescribedby - The ID of the element that describes the modal, for accessibility.
 * @param {string} modalHeading - The heading text displayed at the top of the modal.
 * @param {string} modalDescription - The main descriptive text displayed within the modal.
 * @param {string} modalSubmit - The HTML content for the submit button, allowing customization.
 * @param {HTMLElement} wrapper_element - Optional. The element to which the modal is appended. If not provided, defaults to `document.body`.
 * @param {boolean} forceAction - Optional. If true, adds a `data-force-action` attribute to the modal for additional control.
 *
 * The modal includes a heading, description, submit button, and a cancel button, along with a close button.
 * The `data-close-modal` attribute is added to cancel and close buttons to enable closing functionality.
 */
function addModal(action, id, ariaLabelledby, ariaDescribedby, modalHeading, modalDescription, modalSubmit, wrapper_element, forceAction) {

  const modal = document.createElement('div');
  modal.setAttribute('class', 'usa-modal');
  modal.setAttribute('id', `${action}-${id}`);
  modal.setAttribute('aria-labelledby', ariaLabelledby);
  modal.setAttribute('aria-describedby', ariaDescribedby);
  if (forceAction)
    modal.setAttribute('data-force-action', ''); 

  modal.innerHTML = `
    <div class="usa-modal__content">
      <div class="usa-modal__main">
        <h2 class="usa-modal__heading">
          ${modalHeading}
        </h2>
        <div class="usa-prose">
          <p>
            ${modalDescription}
          </p>
        </div>
        <div class="usa-modal__footer">
            <ul class="usa-button-group">
              <li class="usa-button-group__item">
                ${modalSubmit}
              </li>      
              <li class="usa-button-group__item">
                  <button
                      type="button"
                      class="usa-button usa-button--unstyled padding-105 text-center"
                      data-close-modal
                  >
                      Cancel
                  </button>
              </li>
            </ul>
        </div>
      </div>
      <button
        type="button"
        class="usa-button usa-modal__close"
        aria-label="Close this window"
        data-close-modal
      >
        <svg class="usa-icon" aria-hidden="true" focusable="false" role="img">
          <use xlink:href="/public/img/sprite.svg#close"></use>
        </svg>
      </button>
    </div>
    `
  if (wrapper_element) {
    wrapper_element.appendChild(modal);
  } else {
    document.body.appendChild(modal);
  }
}

/**
 * Helper function that creates a dynamic accordion navigation
 * @param {string} action - The action type or identifier used to create a unique DOM IDs.
 * @param {string} unique_id - An ID that when combined with action makes a unique identifier
 * @param {string} modal_button_text - The action button's text
 * @param {string} screen_reader_text - A screen reader helper
 */
function generateKebabHTML(action, unique_id, modal_button_text, screen_reader_text) {

  const generateModalButton = (mobileOnly = false) => `
    <a 
      role="button" 
      id="button-trigger-${action}-${unique_id}"
      href="#toggle-${action}-${unique_id}"
      class="usa-button usa-button--unstyled text-no-underline late-loading-modal-trigger margin-top-2 line-height-sans-5 text-secondary ${mobileOnly ? 'visible-mobile-flex' : ''}"
      aria-controls="toggle-${action}-${unique_id}"
      data-open-modal
    >
      ${mobileOnly ? `<svg class="usa-icon" aria-hidden="true" focusable="false" role="img" width="24">
        <use xlink:href="/public/img/sprite.svg#delete"></use>
      </svg>` : ''}
      ${modal_button_text}
      <span class="usa-sr-only">${screen_reader_text}</span>
    </a>
  `;

  // Main kebab structure
  const kebab = `
    ${generateModalButton(true)} <!-- Mobile button -->

    <div class="usa-accordion usa-accordion--more-actions margin-right-2 hidden-mobile-flex">
      <div class="usa-accordion__heading">
        <button
          type="button"
          class="usa-button usa-button--unstyled usa-button--with-icon usa-accordion__button usa-button--more-actions"
          aria-expanded="false"
          aria-controls="more-actions-${unique_id}"
        >
          <svg class="usa-icon top-2px" aria-hidden="true" focusable="false" role="img" width="24">
            <use xlink:href="/public/img/sprite.svg#more_vert"></use>
          </svg>
        </button>
      </div>
      <div id="more-actions-${unique_id}" class="usa-accordion__content usa-prose shadow-1 left-auto right-neg-1" hidden>
        <h2>More options</h2>
        ${generateModalButton()} <!-- Desktop button -->
      </div>
    </div>
  `;

  return kebab;
}


/**
 * Toggles expand_more / expand_more svgs in buttons or anchors
 * @param {Element} element - DOM element
 */
function toggleCaret(element) {
  // Get a reference to the use element inside the button
  const useElement = element.querySelector('use');
  // Check if the span element text is 'Hide'
  if (useElement.getAttribute('xlink:href') === '/public/img/sprite.svg#expand_more') {
      // Update the xlink:href attribute to expand_more
      useElement.setAttribute('xlink:href', '/public/img/sprite.svg#expand_less');
  } else {
      // Update the xlink:href attribute to expand_less
      useElement.setAttribute('xlink:href', '/public/img/sprite.svg#expand_more');
  }
}

/**
 * Helper function that scrolls to an element, identified by a class or an id.
 * @param {string} attributeName - The string "class" or "id"
 * @param {string} attributeValue - The class or id used name to identify the element
 */
function ScrollToElement(attributeName, attributeValue) {
  let targetEl = null;

  if (attributeName === 'class') {
    targetEl = document.getElementsByClassName(attributeValue)[0];
  } else if (attributeName === 'id') {
    targetEl = document.getElementById(attributeValue);
  } else {
    console.error('Error: unknown attribute name provided.');
    return; // Exit the function if an invalid attributeName is provided
  }

  if (targetEl) {
    const rect = targetEl.getBoundingClientRect();
    const scrollTop = window.scrollY || document.documentElement.scrollTop;
    window.scrollTo({
      top: rect.top + scrollTop,
      behavior: 'smooth' // Optional: for smooth scrolling
    });
  }
}

/** Creates and returns a live region element. */
function createLiveRegion(id) {
  const liveRegion = document.createElement("div");
  liveRegion.setAttribute("role", "region");
  liveRegion.setAttribute("aria-live", "polite");
  liveRegion.setAttribute("id", id + "-live-region");
  liveRegion.classList.add("usa-sr-only");
  document.body.appendChild(liveRegion);
  return liveRegion;
}

/** Announces changes to assistive technology users. */
function announce(id, text) {
  let liveRegion = document.getElementById(id + "-live-region");
  if (!liveRegion) liveRegion = createLiveRegion(id);
  liveRegion.innerHTML = text;
}

/**
 * Slow down event handlers by limiting how frequently they fire.
 *
 * A wait period must occur with no activity (activity means "this
 * debounce function being called") before the handler is invoked.
 *
 * @param {Function} handler - any JS function
 * @param {number} cooldown - the wait period, in milliseconds
 */
function debounce(handler, cooldown=600) {
  let timeout;
  return function(...args) {
    const context = this;
    clearTimeout(timeout);
    timeout = setTimeout(() => handler.apply(context, args), cooldown);
  }
}

/** Asyncronously fetches JSON. No error handling. */
function fetchJSON(endpoint, callback, url="/api/v1/") {
    const xhr = new XMLHttpRequest();
    xhr.open('GET', url + endpoint);
    xhr.send();
    xhr.onload = function() {
      if (xhr.status != 200) return;
      callback(JSON.parse(xhr.response));
    };
    // nothing, don't care
    // xhr.onerror = function() { };
}

/** Modifies CSS and HTML when an input is valid/invalid. */
function toggleInputValidity(el, valid, msg=DEFAULT_ERROR) {
  if (valid) {
    el.setCustomValidity("");
    el.removeAttribute("aria-invalid");
    el.classList.remove('usa-input--error');
  } else {
    el.classList.remove('usa-input--success');
    el.setAttribute("aria-invalid", "true");
    el.setCustomValidity(msg);
    el.classList.add('usa-input--error');
  }
}

/** Display (or hide) a message beneath an element. */
function inlineToast(el, id, style, msg) {
  if (!el.id && !id) {
    console.error("Elements must have an `id` to show an inline toast.");
    return;
  }
  let toast = document.getElementById((el.id || id) + "--toast");
  if (style) {
    if (!toast) {
      // create and insert the message div
      toast = document.createElement("div");
      const toastBody = document.createElement("div");
      const p = document.createElement("p");
      toast.setAttribute("id", (el.id || id) + "--toast");
      toast.className = `usa-alert usa-alert--${style} usa-alert--slim`;
      toastBody.classList.add("usa-alert__body");
      p.classList.add("usa-alert__text");
      p.innerHTML = msg;
      toastBody.appendChild(p);
      toast.appendChild(toastBody);
      el.parentNode.insertBefore(toast, el.nextSibling);
    } else {
      // update and show the existing message div
      toast.className = `usa-alert usa-alert--${style} usa-alert--slim`;
      toast.querySelector("div p").innerHTML = msg;
      makeVisible(toast);
    }
  } else {
    if (toast) makeHidden(toast);
  }
}

function checkDomainAvailability(el) {
  const callback = (response) => {
    toggleInputValidity(el, (response && response.available), msg=response.message);
    announce(el.id, response.message);

    // Determines if we ignore the field if it is just blank
    ignore_blank = el.classList.contains("blank-ok")
    if (el.validity.valid) {
      el.classList.add('usa-input--success');
      // use of `parentElement` due to .gov inputs being wrapped in www/.gov decoration
      inlineToast(el.parentElement, el.id, SUCCESS, response.message);
    } else if (ignore_blank && response.code == "required"){
      // Visually remove the error
      error = "usa-input--error"
      if (el.classList.contains(error)){
        el.classList.remove(error)
      }
    } else {
      inlineToast(el.parentElement, el.id, ERROR, response.message);
    }
  }
  fetchJSON(`available/?domain=${el.value}`, callback);
}

/** Hides the toast message and clears the aira live region. */
function clearDomainAvailability(el) {
  el.classList.remove('usa-input--success');
  announce(el.id, "");
  // use of `parentElement` due to .gov inputs being wrapped in www/.gov decoration
  inlineToast(el.parentElement, el.id);
}

/** Runs all the validators associated with this element. */
function runValidators(el) {
  const attribute = el.getAttribute("validate") || "";
  if (!attribute.length) return;
  const validators = attribute.split(" ");
  let isInvalid = false;
  for (const validator of validators) {
    switch (validator) {
      case "domain":
        checkDomainAvailability(el);
        break;
    }
  }
  toggleInputValidity(el, !isInvalid);
}

/** Clears all the validators associated with this element. */
function clearValidators(el) {
  const attribute = el.getAttribute("validate") || "";
  if (!attribute.length) return;
  const validators = attribute.split(" ");
  for (const validator of validators) {
    switch (validator) {
      case "domain":
        clearDomainAvailability(el);
        break;
    }
  }
  toggleInputValidity(el, true);
}

/** Hookup listeners for yes/no togglers for form fields 
 * Parameters:
 *  - radioButtonName:  The "name=" value for the radio buttons being used as togglers
 *  - elementIdToShowIfYes: The Id of the element (eg. a div) to show if selected value of the given
 * radio button is true (hides this element if false)
 *  - elementIdToShowIfNo: The Id of the element (eg. a div) to show if selected value of the given
 * radio button is false (hides this element if true)
 * **/
function HookupYesNoListener(radioButtonName, elementIdToShowIfYes, elementIdToShowIfNo) {
  // Get the radio buttons
  let radioButtons = document.querySelectorAll('input[name="'+radioButtonName+'"]');

  function handleRadioButtonChange() {
    // Check the value of the selected radio button
    // Attempt to find the radio button element that is checked
    let radioButtonChecked = document.querySelector('input[name="'+radioButtonName+'"]:checked');

    // Check if the element exists before accessing its value
    let selectedValue = radioButtonChecked ? radioButtonChecked.value : null;

    switch (selectedValue) {
      case 'True':
        toggleTwoDomElements(elementIdToShowIfYes, elementIdToShowIfNo, 1);
        break;

      case 'False':
        toggleTwoDomElements(elementIdToShowIfYes, elementIdToShowIfNo, 2);
        break;

      default:
        toggleTwoDomElements(elementIdToShowIfYes, elementIdToShowIfNo, 0);
    }
  }

  if (radioButtons.length) {
    // Add event listener to each radio button
    radioButtons.forEach(function (radioButton) {
      radioButton.addEventListener('change', handleRadioButtonChange);
    });

    // initialize
    handleRadioButtonChange();
  }
}

// A generic display none/block toggle function that takes an integer param to indicate how the elements toggle
function toggleTwoDomElements(ele1, ele2, index) {
  let element1 = document.getElementById(ele1);
  let element2 = document.getElementById(ele2);
  if (element1 || element2) {
      // Toggle display based on the index
      if (element1) {element1.style.display = index === 1 ? 'block' : 'none';}
      if (element2) {element2.style.display = index === 2 ? 'block' : 'none';}
  } 
  else {
      console.error('Unable to find elements to toggle');
  }
}

// <<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>>
// Event handlers.

/** On input change, handles running any associated validators. */
function handleInputValidation(e) {
  clearValidators(e.target);
  if (e.target.hasAttribute("auto-validate")) runValidators(e.target);
}

/** On button click, handles running any associated validators. */
function validateFieldInput(e) {
  const attribute = e.target.getAttribute("validate-for") || "";
  if (!attribute.length) return;
  const input = document.getElementById(attribute);
  removeFormErrors(input, true);
  runValidators(input);
}


function validateFormsetInputs(e, availabilityButton) {

  // Collect input IDs from the repeatable forms
  let inputs = Array.from(document.querySelectorAll('.repeatable-form input'))

  // Run validators for each input
  inputs.forEach(input => {
    removeFormErrors(input, true);
    runValidators(input);
  });

  // Set the validate-for attribute on the button with the collected input IDs
  // Not needed for functionality but nice for accessibility
  inputs = inputs.map(input => input.id).join(', ');
  availabilityButton.setAttribute('validate-for', inputs);

}

// <<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>>
// Initialization code.

/**
 * An IIFE that will attach validators to inputs.
 *
 * It looks for elements with `validate="<type> <type>"` and adds change handlers.
 * 
 * These handlers know about two other attributes:
 *  - `validate-for="<id>"` creates a button which will run the validator(s) on <id>
 *  - `auto-validate` will run validator(s) when the user stops typing (otherwise,
 *     they will only run when a user clicks the button with `validate-for`)
 */
 (function validatorsInit() {
  "use strict";
  const needsValidation = document.querySelectorAll('[validate]');
  for(const input of needsValidation) {
    input.addEventListener('input', handleInputValidation);
  }
  const alternativeDomainsAvailability = document.getElementById('validate-alt-domains-availability');
  const activatesValidation = document.querySelectorAll('[validate-for]');

  for(const button of activatesValidation) {
    // Adds multi-field validation for alternative domains
    if (button === alternativeDomainsAvailability) {
      button.addEventListener('click', (e) => {
        validateFormsetInputs(e, alternativeDomainsAvailability)
      });
    } else {
      button.addEventListener('click', validateFieldInput);
    }
  }
})();

/**
 * Removes form errors surrounding a form input
 */
function removeFormErrors(input, removeStaleAlerts=false){
  // Remove error message
  let errorMessage = document.getElementById(`${input.id}__error-message`);
  if (errorMessage) {
    errorMessage.remove();
  }else{
    return
  }

  // Remove error classes
  if (input.classList.contains('usa-input--error')) {
    input.classList.remove('usa-input--error');
  }

  // Get the form label
  let label = document.querySelector(`label[for="${input.id}"]`);
  if (label) {
    label.classList.remove('usa-label--error');

    // Remove error classes from parent div
    let parentDiv = label.parentElement;
    if (parentDiv) {
      parentDiv.classList.remove('usa-form-group--error');
    }
  }

  if (removeStaleAlerts){
    let staleAlerts = document.querySelectorAll(".usa-alert--error")
    for (let alert of staleAlerts){
      // Don't remove the error associated with the input
      if (alert.id !== `${input.id}--toast`) {
        alert.remove()
      }
    }
  }
}

/**
 * Prepare the namerservers and DS data forms delete buttons
 * We will call this on the forms init, and also every time we add a form
 * 
 */
function removeForm(e, formLabel, isNameserversForm, addButton, formIdentifier){
  let totalForms = document.querySelector(`#id_${formIdentifier}-TOTAL_FORMS`);
  let formToRemove = e.target.closest(".repeatable-form");
  formToRemove.remove();
  let forms = document.querySelectorAll(".repeatable-form");
  totalForms.setAttribute('value', `${forms.length}`);

  let formNumberRegex = RegExp(`form-(\\d){1}-`, 'g');
  let formLabelRegex = RegExp(`${formLabel} (\\d+){1}`, 'g');
  // For the example on Nameservers
  let formExampleRegex = RegExp(`ns(\\d+){1}`, 'g');

  forms.forEach((form, index) => {
    // Iterate over child nodes of the current element
    Array.from(form.querySelectorAll('label, input, select')).forEach((node) => {
      // Iterate through the attributes of the current node
      Array.from(node.attributes).forEach((attr) => {
        // Check if the attribute value matches the regex
        if (formNumberRegex.test(attr.value)) {
          // Replace the attribute value with the updated value
          attr.value = attr.value.replace(formNumberRegex, `form-${index}-`);
        }
      });
    });

    // h2 and legend for DS form, label for nameservers  
    Array.from(form.querySelectorAll('h2, legend, label, p')).forEach((node) => {

      let innerSpan = node.querySelector('span')
      if (innerSpan) {
        innerSpan.textContent = innerSpan.textContent.replace(formLabelRegex, `${formLabel} ${index + 1}`);
      } else {
        node.textContent = node.textContent.replace(formLabelRegex, `${formLabel} ${index + 1}`);
        node.textContent = node.textContent.replace(formExampleRegex, `ns${index + 1}`);
      }
      
      // If the node is a nameserver label, one of the first 2 which was previously 3 and up (not required)
      // inject the USWDS required markup and make sure the INPUT is required
      if (isNameserversForm && index <= 1 && node.innerHTML.includes('server') && !node.innerHTML.includes('*')) {

        // Remove the word optional
        innerSpan.textContent = innerSpan.textContent.replace(/\s*\(\s*optional\s*\)\s*/, '');

        // Create a new element
        const newElement = document.createElement('abbr');
        newElement.textContent = '*';
        newElement.setAttribute("title", "required");
        newElement.classList.add("usa-hint", "usa-hint--required");

        // Append the new element to the label
        node.appendChild(newElement);
        // Find the next sibling that is an input element
        let nextInputElement = node.nextElementSibling;

        while (nextInputElement) {
          if (nextInputElement.tagName === 'INPUT') {
            // Found the next input element
            nextInputElement.setAttribute("required", "")
            break;
          }
          nextInputElement = nextInputElement.nextElementSibling;
        }
        nextInputElement.required = true;
      }

      
    
    });

    // Display the add more button if we have less than 13 forms
    if (isNameserversForm && forms.length <= 13) {
      addButton.removeAttribute("disabled");
    }

    if (isNameserversForm && forms.length < 3) {
      // Hide the delete buttons on the remaining nameservers
      Array.from(form.querySelectorAll('.delete-record')).forEach((deleteButton) => {
        deleteButton.setAttribute("disabled", "true");
      });
    }
  
  });
}

/**
 * Delete method for formsets using the DJANGO DELETE widget (Other Contacts)
 * 
 */
function markForm(e, formLabel){
  // Unlike removeForm, we only work with the visible forms when using DJANGO's DELETE widget
  let totalShownForms = document.querySelectorAll(`.repeatable-form:not([style*="display: none"])`).length;

  if (totalShownForms == 1) {
    // toggle the radio buttons
    let radioButton = document.querySelector('input[name="other_contacts-has_other_contacts"][value="False"]');
    radioButton.checked = true;
    // Trigger the change event
    let event = new Event('change');
    radioButton.dispatchEvent(event);
  } else {

    // Grab the hidden delete input and assign a value DJANGO will look for
    let formToRemove = e.target.closest(".repeatable-form");
    if (formToRemove) {
      let deleteInput = formToRemove.querySelector('input[class="deletion"]');
      if (deleteInput) {
        deleteInput.value = 'on';
      }
    }

    // Set display to 'none'
    formToRemove.style.display = 'none';
  }
  
  // Update h2s on the visible forms only. We won't worry about the forms' identifiers
  let shownForms = document.querySelectorAll(`.repeatable-form:not([style*="display: none"])`);
  let formLabelRegex = RegExp(`${formLabel} (\\d+){1}`, 'g');
  shownForms.forEach((form, index) => {
    // Iterate over child nodes of the current element
    Array.from(form.querySelectorAll('h2')).forEach((node) => {
        node.textContent = node.textContent.replace(formLabelRegex, `${formLabel} ${index + 1}`);
    });
  });
}

/**
 * Prepare the namerservers, DS data and Other Contacts formsets' delete button
 * for the last added form. We call this from the Add function
 * 
 */
function prepareNewDeleteButton(btn, formLabel) {
  let formIdentifier = "form"
  let isNameserversForm = document.querySelector(".nameservers-form");
  let isOtherContactsForm = document.querySelector(".other-contacts-form");
  let addButton = document.querySelector("#add-form");

  if (isOtherContactsForm) {
    formIdentifier = "other_contacts";
    // We will mark the forms for deletion
    btn.addEventListener('click', function(e) {
      markForm(e, formLabel);
    });
  } else {
    // We will remove the forms and re-order the formset
    btn.addEventListener('click', function(e) {
      removeForm(e, formLabel, isNameserversForm, addButton, formIdentifier);
    });
  }
}

/**
 * Prepare the namerservers, DS data and Other Contacts formsets' delete buttons
 * We will call this on the forms init
 * 
 */
function prepareDeleteButtons(formLabel) {
  let formIdentifier = "form"
  let deleteButtons = document.querySelectorAll(".delete-record");
  let isNameserversForm = document.querySelector(".nameservers-form");
  let isOtherContactsForm = document.querySelector(".other-contacts-form");
  let addButton = document.querySelector("#add-form");
  if (isOtherContactsForm) {
    formIdentifier = "other_contacts";
  }
  
  // Loop through each delete button and attach the click event listener
  deleteButtons.forEach((deleteButton) => {
    if (isOtherContactsForm) {
      // We will mark the forms for deletion
      deleteButton.addEventListener('click', function(e) {
        markForm(e, formLabel);
      });
    } else {
      // We will remove the forms and re-order the formset
      deleteButton.addEventListener('click', function(e) {
        removeForm(e, formLabel, isNameserversForm, addButton, formIdentifier);
      });
    }
  });
}

/**
 * DJANGO formset's DELETE widget
 * On form load, hide deleted forms, ie. those forms with hidden input of class 'deletion'
 * with value='on'
 */
function hideDeletedForms() {
  let hiddenDeleteButtonsWithValueOn = document.querySelectorAll('input[type="hidden"].deletion[value="on"]');

  // Iterating over the NodeList of hidden inputs
  hiddenDeleteButtonsWithValueOn.forEach(function(hiddenInput) {
      // Finding the closest parent element with class "repeatable-form" for each hidden input
      var repeatableFormToHide = hiddenInput.closest('.repeatable-form');
  
      // Checking if a matching parent element is found for each hidden input
      if (repeatableFormToHide) {
          // Setting the display property to "none" for each matching parent element
          repeatableFormToHide.style.display = 'none';
      }
  });
}

// Checks for if we want to display Urbanization or not
document.addEventListener('DOMContentLoaded', function() {
  var stateTerritoryField = document.querySelector('select[name="organization_contact-state_territory"]');

  if (!stateTerritoryField) {
    return; // Exit if the field not found
  }

  setupUrbanizationToggle(stateTerritoryField);
});

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

/**
 * An IIFE that attaches a click handler for our dynamic formsets
 *
 * Only does something on a few pages, but it should be fast enough to run
 * it everywhere.
 */
(function prepareFormsetsForms() {
  let formIdentifier = "form"
  let repeatableForm = document.querySelectorAll(".repeatable-form");
  let container = document.querySelector("#form-container");
  let addButton = document.querySelector("#add-form");
  let cloneIndex = 0;
  let formLabel = '';
  let isNameserversForm = document.querySelector(".nameservers-form");
  let isOtherContactsForm = document.querySelector(".other-contacts-form");
  let isDsDataForm = document.querySelector(".ds-data-form");
  let isDotgovDomain = document.querySelector(".dotgov-domain-form");
  // The Nameservers formset features 2 required and 11 optionals
  if (isNameserversForm) {
    // cloneIndex = 2;
    formLabel = "Name server";
  // DNSSEC: DS Data
  } else if (isDsDataForm) {
    formLabel = "DS data record";
  // The Other Contacts form
  } else if (isOtherContactsForm) {
    formLabel = "Organization contact";
    container = document.querySelector("#other-employees");
    formIdentifier = "other_contacts"
  } else if (isDotgovDomain) {
    formIdentifier = "dotgov_domain"
  }
  let totalForms = document.querySelector(`#id_${formIdentifier}-TOTAL_FORMS`);

  // On load: Disable the add more button if we have 13 forms
  if (isNameserversForm && document.querySelectorAll(".repeatable-form").length == 13) {
    addButton.setAttribute("disabled", "true");
  }

  // Hide forms which have previously been deleted
  hideDeletedForms()

  // Attach click event listener on the delete buttons of the existing forms
  prepareDeleteButtons(formLabel);

  if (addButton)
    addButton.addEventListener('click', addForm);

  function addForm(e){
      let forms = document.querySelectorAll(".repeatable-form");
      let formNum = forms.length;
      let newForm = repeatableForm[cloneIndex].cloneNode(true);
      let formNumberRegex = RegExp(`${formIdentifier}-(\\d){1}-`,'g');
      let formLabelRegex = RegExp(`${formLabel} (\\d){1}`, 'g');
      // For the eample on Nameservers
      let formExampleRegex = RegExp(`ns(\\d){1}`, 'g');

      // Some Nameserver form checks since the delete can mess up the source object we're copying
      // in regards to required fields and hidden delete buttons
      if (isNameserversForm) {

        // If the source element we're copying has required on an input,
        // reset that input
        let formRequiredNeedsCleanUp = newForm.innerHTML.includes('*');
        if (formRequiredNeedsCleanUp) {
          newForm.querySelector('label abbr').remove();
          // Get all input elements within the container
          const inputElements = newForm.querySelectorAll("input");
          // Loop through each input element and remove the 'required' attribute
          inputElements.forEach((input) => {
            if (input.hasAttribute("required")) {
              input.removeAttribute("required");
            }
          });
        }

        // If the source element we're copying has an disabled delete button,
        // enable that button
        let deleteButton= newForm.querySelector('.delete-record');
        if (deleteButton.hasAttribute("disabled")) {
          deleteButton.removeAttribute("disabled");
        }
      }

      formNum++;

      newForm.innerHTML = newForm.innerHTML.replace(formNumberRegex, `${formIdentifier}-${formNum-1}-`);
      if (isOtherContactsForm) {
        // For the other contacts form, we need to update the fieldset headers based on what's visible vs hidden,
        // since the form on the backend employs Django's DELETE widget.
        let totalShownForms = document.querySelectorAll(`.repeatable-form:not([style*="display: none"])`).length;
        newForm.innerHTML = newForm.innerHTML.replace(formLabelRegex, `${formLabel} ${totalShownForms + 1}`);
      } else {
        // Nameservers form is cloned from index 2 which has the word optional on init, does not have the word optional
        // if indices 0 or 1 have been deleted
        let containsOptional = newForm.innerHTML.includes('(optional)');
        if (isNameserversForm && !containsOptional) {
          newForm.innerHTML = newForm.innerHTML.replace(formLabelRegex, `${formLabel} ${formNum} (optional)`);
        } else {
          newForm.innerHTML = newForm.innerHTML.replace(formLabelRegex, `${formLabel} ${formNum}`);
        }
      }
      newForm.innerHTML = newForm.innerHTML.replace(formExampleRegex, `ns${formNum}`);
      newForm.innerHTML = newForm.innerHTML.replace(/\n/g, '');  // Remove newline characters
      newForm.innerHTML = newForm.innerHTML.replace(/>\s*</g, '><');  // Remove spaces between tags
      container.insertBefore(newForm, addButton);

      newForm.style.display = 'block';

      let inputs = newForm.querySelectorAll("input");
      // Reset the values of each input to blank
      inputs.forEach((input) => {
        input.classList.remove("usa-input--error");
        input.classList.remove("usa-input--success");
        if (input.type === "text" || input.type === "number" || input.type === "password" || input.type === "email" || input.type === "tel") {
          input.value = ""; // Set the value to an empty string
          
        } else if (input.type === "checkbox" || input.type === "radio") {
          input.checked = false; // Uncheck checkboxes and radios
        }
      });

      // Reset any existing validation classes
      let selects = newForm.querySelectorAll("select");
      selects.forEach((select) => {
        select.classList.remove("usa-input--error");
        select.classList.remove("usa-input--success");
        select.selectedIndex = 0; // Set the value to an empty string
      });

      let labels = newForm.querySelectorAll("label");
      labels.forEach((label) => {
        label.classList.remove("usa-label--error");
        label.classList.remove("usa-label--success");
      });

      let usaFormGroups = newForm.querySelectorAll(".usa-form-group");
      usaFormGroups.forEach((usaFormGroup) => {
        usaFormGroup.classList.remove("usa-form-group--error");
        usaFormGroup.classList.remove("usa-form-group--success");
      });

      // Remove any existing error and success messages
      let usaMessages = newForm.querySelectorAll(".usa-error-message, .usa-alert");
      usaMessages.forEach((usaErrorMessage) => {
        let parentDiv = usaErrorMessage.closest('div');
        if (parentDiv) {
          parentDiv.remove(); // Remove the parent div if it exists
        }
      });

      totalForms.setAttribute('value', `${formNum}`);

      // Attach click event listener on the delete buttons of the new form
      let newDeleteButton = newForm.querySelector(".delete-record");
      if (newDeleteButton)
        prepareNewDeleteButton(newDeleteButton, formLabel);

      // Disable the add more button if we have 13 forms
      if (isNameserversForm && formNum == 13) {
        addButton.setAttribute("disabled", "true");
      }

      if (isNameserversForm && forms.length >= 2) {
        // Enable the delete buttons on the nameservers
        forms.forEach((form, index) => {
          Array.from(form.querySelectorAll('.delete-record')).forEach((deleteButton) => {
            deleteButton.removeAttribute("disabled");
          });
        });
      }
  }
})();

/**
 * An IIFE that triggers a modal on the DS Data Form under certain conditions
 *
 */
(function triggerModalOnDsDataForm() {
  let saveButon = document.querySelector("#save-ds-data");

  // The view context will cause a hitherto hidden modal trigger to
  // show up. On save, we'll test for that modal trigger appearing. We'll
  // run that test once every 100 ms for 5 secs, which should balance performance
  // while accounting for network or lag issues.
  if (saveButon) {
    let i = 0;
    var tryToTriggerModal = setInterval(function() {
        i++;
        if (i > 100) {
          clearInterval(tryToTriggerModal);
        }
        let modalTrigger = document.querySelector("#ds-toggle-dnssec-alert");
        if (modalTrigger) {
          modalTrigger.click()
          clearInterval(tryToTriggerModal);
        }
    }, 50);
  }
})();


/**
 * An IIFE that listens to the other contacts radio form on DAs and toggles the contacts/no other contacts forms 
 *
 */
(function otherContactsFormListener() {
  HookupYesNoListener("other_contacts-has_other_contacts",'other-employees', 'no-other-employees')
})();


/**
 * An IIFE that listens to the yes/no radio buttons on the anything else form and toggles form field visibility accordingly
 *
 */
(function anythingElseFormListener() {
  HookupYesNoListener("additional_details-has_anything_else_text",'anything-else', null)
})();

/**
 * An IIFE that disables the delete buttons on nameserver forms on page load if < 3 forms
 *
 */
(function nameserversFormListener() {
  let isNameserversForm = document.querySelector(".nameservers-form");
  if (isNameserversForm) {
    let forms = document.querySelectorAll(".repeatable-form");
    if (forms.length < 3) {
      // Hide the delete buttons on the 2 nameservers
      forms.forEach((form) => {
        Array.from(form.querySelectorAll('.delete-record')).forEach((deleteButton) => {
          deleteButton.setAttribute("disabled", "true");
        });
      });
    }
  }
})();

/**
 * An IIFE that disables the delete buttons on nameserver forms on page load if < 3 forms
 *
 */
(function nameserversFormListener() {
  let isNameserversForm = document.querySelector(".nameservers-form");
  if (isNameserversForm) {
    let forms = document.querySelectorAll(".repeatable-form");
    if (forms.length < 3) {
      // Hide the delete buttons on the 2 nameservers
      forms.forEach((form) => {
        Array.from(form.querySelectorAll('.delete-record')).forEach((deleteButton) => {
          deleteButton.setAttribute("disabled", "true");
        });
      });
    }
  }
})();

/**
 * An IIFE that listens to the yes/no radio buttons on the CISA representatives form and toggles form field visibility accordingly
 *
 */
(function cisaRepresentativesFormListener() {
  HookupYesNoListener("additional_details-has_cisa_representative",'cisa-representative', null)
})();

/**
 * Initialize USWDS tooltips by calling initialization method.  Requires that uswds-edited.js
 * be loaded before get-gov.js.  uswds-edited.js adds the tooltip module to the window to be
 * accessible directly in get-gov.js
 * 
 */
function initializeTooltips() {
  function checkTooltip() {
    // Check that the tooltip library is loaded, and if not, wait and retry
    if (window.tooltip && typeof window.tooltip.init === 'function') {
        window.tooltip.init();
    } else {
        // Retry after a short delay
        setTimeout(checkTooltip, 100);
    }
  }
  checkTooltip();
}

/**
 * Initialize USWDS modals by calling on method.  Requires that uswds-edited.js be loaded
 * before get-gov.js.  uswds-edited.js adds the modal module to the window to be accessible
 * directly in get-gov.js.
 * initializeModals adds modal-related DOM elements, based on other DOM elements existing in 
 * the page.  It needs to be called only once for any particular DOM element; otherwise, it
 * will initialize improperly.  Therefore, if DOM elements change dynamically and include
 * DOM elements with modal classes, uswdsUnloadModals needs to be called before initializeModals.
 * 
 */
function uswdsInitializeModals() {
    window.modal.on();

}

/**
 * Unload existing USWDS modals by calling off method.  Requires that uswds-edited.js be
 * loaded before get-gov.js.  uswds-edited.js adds the modal module to the window to be
 * accessible directly in get-gov.js.
 * See note above with regards to calling this method relative to initializeModals.
 * 
 */
function uswdsUnloadModals() {
  window.modal.off();
}

/**
 * Base table class which handles search, retrieval, rendering and interaction with results.
 * Classes can extend the basic behavior of this class to customize display and interaction.
 */
class BaseTable {
  constructor(itemName) {
    this.itemName = itemName;
    this.sectionSelector = itemName + 's';
    this.tableWrapper = document.getElementById(`${this.sectionSelector}__table-wrapper`);
    this.tableHeaders = document.querySelectorAll(`#${this.sectionSelector} th[data-sortable]`);
    this.currentSortBy = 'id';
    this.currentOrder = 'asc';
    this.currentStatus = [];
    this.currentSearchTerm = '';
    this.scrollToTable = false;
    this.searchInput = document.getElementById(`${this.sectionSelector}__search-field`);
    this.searchSubmit = document.getElementById(`${this.sectionSelector}__search-field-submit`);
    this.tableAnnouncementRegion = document.getElementById(`${this.sectionSelector}__usa-table__announcement-region`);
    this.resetSearchButton = document.getElementById(`${this.sectionSelector}__reset-search`);
    this.resetFiltersButton = document.getElementById(`${this.sectionSelector}__reset-filters`);
    this.statusCheckboxes = document.querySelectorAll(`.${this.sectionSelector} input[name="filter-status"]`);
    this.statusIndicator = document.getElementById(`${this.sectionSelector}__filter-indicator`);
    this.statusToggle = document.getElementById(`${this.sectionSelector}__usa-button--filter`);
    this.noTableWrapper = document.getElementById(`${this.sectionSelector}__no-data`);
    this.noSearchResultsWrapper = document.getElementById(`${this.sectionSelector}__no-search-results`);
    this.portfolioElement = document.getElementById('portfolio-js-value');
    this.portfolioValue = this.portfolioElement ? this.portfolioElement.getAttribute('data-portfolio') : null;
    this.initializeTableHeaders();
    this.initializeSearchHandler();
    this.initializeStatusToggleHandler();
    this.initializeFilterCheckboxes();
    this.initializeResetSearchButton();
    this.initializeResetFiltersButton();
    this.initializeAccordionAccessibilityListeners();
  }

  /**
   * Generalized function to update pagination for a list.
   * @param {number} currentPage - The current page number (starting with 1).
   * @param {number} numPages - The total number of pages.
   * @param {boolean} hasPrevious - Whether there is a page before the current page.
   * @param {boolean} hasNext - Whether there is a page after the current page.
   * @param {number} total - The total number of items.
   */  
  updatePagination(
    currentPage,
    numPages,
    hasPrevious,
    hasNext,
    totalItems,
  ) {
    const paginationButtons = document.querySelector(`#${this.sectionSelector}-pagination .usa-pagination__list`);
    const counterSelectorEl = document.querySelector(`#${this.sectionSelector}-pagination .usa-pagination__counter`);
    const paginationSelectorEl = document.querySelector(`#${this.sectionSelector}-pagination`);
    const parentTableSelector = `#${this.sectionSelector}`;
    counterSelectorEl.innerHTML = '';
    paginationButtons.innerHTML = '';

    // Buttons should only be displayed if there are more than one pages of results
    paginationButtons.classList.toggle('display-none', numPages <= 1);

    // Counter should only be displayed if there is more than 1 item
    paginationSelectorEl.classList.toggle('display-none', totalItems < 1);

    counterSelectorEl.innerHTML = `${totalItems} ${this.itemName}${totalItems > 1 ? 's' : ''}${this.currentSearchTerm ? ' for ' + '"' + this.currentSearchTerm + '"' : ''}`;

    // Helper function to create a pagination item, such as a 
    const createPaginationItem = (page) => {
      const paginationItem = document.createElement('li');
      paginationItem.className = 'usa-pagination__item usa-pagination__page-no';
      paginationItem.innerHTML = `
        <a href="${parentTableSelector}" class="usa-pagination__button" aria-label="Page ${page}">${page}</a>
      `;
      if (page === currentPage) {
        paginationItem.querySelector('a').classList.add('usa-current');
        paginationItem.querySelector('a').setAttribute('aria-current', 'page');
      }
      paginationItem.querySelector('a').addEventListener('click', (event) => {
        event.preventDefault();
        this.loadTable(page);
      });
      return paginationItem;
    };

    if (hasPrevious) {
      const prevPaginationItem = document.createElement('li');
      prevPaginationItem.className = 'usa-pagination__item usa-pagination__arrow';
      prevPaginationItem.innerHTML = `
        <a href="${parentTableSelector}" class="usa-pagination__link usa-pagination__previous-page" aria-label="Previous page">
          <svg class="usa-icon" aria-hidden="true" role="img">
            <use xlink:href="/public/img/sprite.svg#navigate_before"></use>
          </svg>
          <span class="usa-pagination__link-text">Previous</span>
        </a>
      `;
      prevPaginationItem.querySelector('a').addEventListener('click', (event) => {
        event.preventDefault();
        this.loadTable(currentPage - 1);
      });
      paginationButtons.appendChild(prevPaginationItem);
    }

    // Add first page and ellipsis if necessary
    if (currentPage > 2) {
      paginationButtons.appendChild(createPaginationItem(1));
      if (currentPage > 3) {
        const ellipsis = document.createElement('li');
        ellipsis.className = 'usa-pagination__item usa-pagination__overflow';
        ellipsis.setAttribute('aria-label', 'ellipsis indicating non-visible pages');
        ellipsis.innerHTML = '<span>…</span>';
        paginationButtons.appendChild(ellipsis);
      }
    }

    // Add pages around the current page
    for (let i = Math.max(1, currentPage - 1); i <= Math.min(numPages, currentPage + 1); i++) {
      paginationButtons.appendChild(createPaginationItem(i));
    }

    // Add last page and ellipsis if necessary
    if (currentPage < numPages - 1) {
      if (currentPage < numPages - 2) {
        const ellipsis = document.createElement('li');
        ellipsis.className = 'usa-pagination__item usa-pagination__overflow';
        ellipsis.setAttribute('aria-label', 'ellipsis indicating non-visible pages');
        ellipsis.innerHTML = '<span>…</span>';
        paginationButtons.appendChild(ellipsis);
      }
      paginationButtons.appendChild(createPaginationItem(numPages));
    }

    if (hasNext) {
      const nextPaginationItem = document.createElement('li');
      nextPaginationItem.className = 'usa-pagination__item usa-pagination__arrow';
      nextPaginationItem.innerHTML = `
        <a href="${parentTableSelector}" class="usa-pagination__link usa-pagination__next-page" aria-label="Next page">
          <span class="usa-pagination__link-text">Next</span>
          <svg class="usa-icon" aria-hidden="true" role="img">
            <use xlink:href="/public/img/sprite.svg#navigate_next"></use>
          </svg>
        </a>
      `;
      nextPaginationItem.querySelector('a').addEventListener('click', (event) => {
        event.preventDefault();
        this.loadTable(currentPage + 1);
      });
      paginationButtons.appendChild(nextPaginationItem);
    }
  }

  /**
   * A helper that toggles content/ no content/ no search results based on results in data.
   * @param {Object} data - Data representing current page of results data.
   * @param {HTMLElement} dataWrapper - The DOM element to show if there are results on the current page.
   * @param {HTMLElement} noDataWrapper - The DOM element to show if there are no results period.
   * @param {HTMLElement} noSearchResultsWrapper - The DOM element to show if there are no results in the current filtered search.
   */
  updateDisplay = (data, dataWrapper, noDataWrapper, noSearchResultsWrapper) => {
    const { unfiltered_total, total } = data;
    if (unfiltered_total) {
      if (total) {
        showElement(dataWrapper);
        hideElement(noSearchResultsWrapper);
        hideElement(noDataWrapper);
      } else {
        hideElement(dataWrapper);
        showElement(noSearchResultsWrapper);
        hideElement(noDataWrapper);
      }
    } else {
      hideElement(dataWrapper);
      hideElement(noSearchResultsWrapper);
      showElement(noDataWrapper);
    }
  };

  /**
   * A helper that resets sortable table headers
   *
  */
  unsetHeader = (header) => {
    header.removeAttribute('aria-sort');
    let headerName = header.innerText;
    const headerLabel = `${headerName}, sortable column, currently unsorted"`;
    const headerButtonLabel = `Click to sort by ascending order.`;
    header.setAttribute("aria-label", headerLabel);
    header.querySelector('.usa-table__header__button').setAttribute("title", headerButtonLabel);
  };


  /**
   * Generates search params for filtering and sorting
   * @param {number} page - The current page number for pagination (starting with 1)
   * @param {*} sortBy - The sort column option
   * @param {*} order - The order of sorting {asc, desc}
   * @param {string} searchTerm - The search term used to filter results for a specific keyword
   * @param {*} status - The status filter applied {ready, dns_needed, etc}
   * @param {string} portfolio - The portfolio id
   */
  #getSearchParams(page, sortBy, order, searchTerm, status, portfolio) {
    let searchParams = new URLSearchParams(
      {
        "page": page,
        "sort_by": sortBy,
        "order": order,
        "search_term": searchTerm,
      }
    );

    let emailValue = this.portfolioElement ? this.portfolioElement.getAttribute('data-email') : null;
    let memberIdValue = this.portfolioElement ? this.portfolioElement.getAttribute('data-member-id') : null;
    let memberOnly = this.portfolioElement ? this.portfolioElement.getAttribute('data-member-only') : null;

    if (portfolio)
      searchParams.append("portfolio", portfolio);
    if (emailValue)
      searchParams.append("email", emailValue);
    if (memberIdValue)
      searchParams.append("member_id", memberIdValue);
    if (memberOnly)
      searchParams.append("member_only", memberOnly);
    if (status)
      searchParams.append("status", status);
    return searchParams;
  }

  /**
   * Gets the base URL of API requests
   * Placeholder function in a parent class - method should be implemented by child class for specifics
   * Throws an error if called directly from the parent class
   */
  getBaseUrl() {
    throw new Error('getBaseUrl must be defined');
  }

  /**
   * Calls "uswdsUnloadModals" to remove any existing modal element to make sure theres no unintended consequences 
   * from leftover event listeners + can be properly re-initialized
   */
  unloadModals(){}

  /**
   * Initializes modals + sets up event listeners for the modal submit actions
   * "Activates" the modals after the DOM updates 
   * Utilizes "uswdsInitializeModals"
   * Adds click event listeners to each modal's submit button so we can handle a user's actions
   *
   * When the submit button is clicked:
   * - Triggers the close button to reset modal classes
   * - Determines if the page needs refreshing if the last item is deleted
   * @param {number} page - The current page number for pagination
   * @param {number} total - The total # of items on the current page
   * @param {number} unfiltered_total - The total # of items across all pages
   */
  initializeModals(page, total, unfiltered_total) {}
  
  /**
   * Allows us to customize the table display based on specific conditions and a user's permissions
   * Dynamically manages the visibility set up of columns, adding/removing headers 
   * (ie if a domain request is deleteable, we include the kebab column or if a user has edit permissions
   * for a member, they will also see the kebab column)
   * @param {Object} dataObjects - Data which contains info on domain requests or a user's permission
   * Currently returns a dictionary of either:
   * - "needsAdditionalColumn": If a new column should be displayed 
   * - "UserPortfolioPermissionChoices": A user's portfolio permission choices 
   */
  customizeTable(dataObjects){ return {}; }

  /**
   * Abstract method for retrieving specific data objects from the provided data set.
   * This method should be implemented by child classes to extract and return a specific
   * subset of data (e.g., `members`, `domains`, or `domain_requests`) based on the class's context.
   * 
   * Expected implementations:
   * - Could return `data.members`, `data.domains`, `data.domain_requests`, etc., depending on the child class.
   * 
   * @param {Object} data - The full data set from which a subset of objects is extracted.
   * @throws {Error} Throws an error if not implemented in a child class.
   * @returns {Array|Object} The extracted data subset, as defined in the child class.
   */

  /**
   * Retrieves specific data objects
   * Placeholder function in a parent class - method should be implemented by child class for specifics
   * Throws an error if called directly from the parent class
   * Returns either: data.members, data.domains or data.domain_requests
   * @param {Object} data - The full data set from which a subset of objects is extracted.
   */
  getDataObjects(data) {
    throw new Error('getDataObjects must be defined');
  }

  /**
   * Creates + appends a row to a tbody element
   * Tailored structure set up for each data object (domain, domain_request, member, etc) 
   * Placeholder function in a parent class - method should be implemented by child class for specifics
   * Throws an error if called directly from the parent class
   * Returns either: data.members, data.domains or data.domain_requests
   * @param {Object} dataObject - The data used to populate the row content 
   * @param {HTMLElement} tbody - The table body to which the new row is appended to 
   * @param {Object} customTableOptions - Additional options for customizing row appearance (ie needsAdditionalColumn)
   */
  addRow(dataObject, tbody, customTableOptions) {
    throw new Error('addRow must be defined');
  }

   /**
   * See function for more details
   */
  initShowMoreButtons(){}

  /**
   * Loads rows in the members list, as well as updates pagination around the members list
   * based on the supplied attributes.
   * @param {*} page - The page number of the results (starts with 1)
   * @param {*} sortBy - The sort column option
   * @param {*} order - The sort order {asc, desc}
   * @param {*} scroll - The control for the scrollToElement functionality
   * @param {*} searchTerm - The search term
   * @param {*} portfolio - The portfolio id
   */
  loadTable(page, sortBy = this.currentSortBy, order = this.currentOrder, scroll = this.scrollToTable, status = this.currentStatus, searchTerm =this.currentSearchTerm, portfolio = this.portfolioValue) {
    // --------- SEARCH
    let searchParams = this.#getSearchParams(page, sortBy, order, searchTerm, status, portfolio); 

    // --------- FETCH DATA
    // fetch json of page of domains, given params
    let baseUrl = this.getBaseUrl();

    if (!baseUrl) {
      return;
    }

    let baseUrlValue = baseUrl.innerHTML;
    if (!baseUrlValue) {
      return;
    }
    
    let url = `${baseUrlValue}?${searchParams.toString()}` //TODO: uncomment for search function
    fetch(url)
      .then(response => response.json())
      .then(data => {
        if (data.error) {
          console.error('Error in AJAX call: ' + data.error);
          return;
        }

        // handle the display of proper messaging in the event that no members exist in the list or search returns no results
        this.updateDisplay(data, this.tableWrapper, this.noTableWrapper, this.noSearchResultsWrapper, this.currentSearchTerm);

        // identify the DOM element where the list of results will be inserted into the DOM
        const tbody = this.tableWrapper.querySelector('tbody');
        tbody.innerHTML = '';

        // remove any existing modal elements from the DOM so they can be properly re-initialized
        // after the DOM content changes and there are new delete modal buttons added
        this.unloadModals();

        let dataObjects = this.getDataObjects(data);
        let customTableOptions = this.customizeTable(data);

        dataObjects.forEach(dataObject => {
          this.addRow(dataObject, tbody, customTableOptions);
        });
        
        this.initShowMoreButtons();

        this.initializeModals(data.page, data.total, data.unfiltered_total);

        // Do not scroll on first page load
        if (scroll)
          ScrollToElement('class', this.sectionSelector);
        this.scrollToTable = true;

        // update pagination
        this.updatePagination(
          data.page,
          data.num_pages,
          data.has_previous,
          data.has_next,
          data.total,
        );
        this.currentSortBy = sortBy;
        this.currentOrder = order;
        this.currentSearchTerm = searchTerm;
    })
    .catch(error => console.error('Error fetching objects:', error));
  }


  // Add event listeners to table headers for sorting
  initializeTableHeaders() {
    this.tableHeaders.forEach(header => {
      header.addEventListener('click', () => {
        const sortBy = header.getAttribute('data-sortable');
        let order = 'asc';
        // sort order will be ascending, unless the currently sorted column is ascending, and the user
        // is selecting the same column to sort in descending order
        if (sortBy === this.currentSortBy) {
          order = this.currentOrder === 'asc' ? 'desc' : 'asc';
        }
        // load the results with the updated sort
        this.loadTable(1, sortBy, order);
      });
    });
  }

  initializeSearchHandler() {
    this.searchSubmit.addEventListener('click', (e) => {
      e.preventDefault();
      this.currentSearchTerm = this.searchInput.value;
      // If the search is blank, we match the resetSearch functionality
      if (this.currentSearchTerm) {
        showElement(this.resetSearchButton);
      } else {
        hideElement(this.resetSearchButton);
      }
      this.loadTable(1, 'id', 'asc');
      this.resetHeaders();
    });
  }

  initializeStatusToggleHandler() {
    if (this.statusToggle) {
      this.statusToggle.addEventListener('click', () => {
        toggleCaret(this.statusToggle);
      });
    }
  }

  // Add event listeners to status filter checkboxes
  initializeFilterCheckboxes() {
    this.statusCheckboxes.forEach(checkbox => {
      checkbox.addEventListener('change', () => {
        const checkboxValue = checkbox.value;
        
        // Update currentStatus array based on checkbox state
        if (checkbox.checked) {
          this.currentStatus.push(checkboxValue);
        } else {
          const index = this.currentStatus.indexOf(checkboxValue);
          if (index > -1) {
            this.currentStatus.splice(index, 1);
          }
        }

        // Manage visibility of reset filters button
        if (this.currentStatus.length == 0) {
          hideElement(this.resetFiltersButton);
        } else {
          showElement(this.resetFiltersButton);
        }

        // Disable the auto scroll
        this.scrollToTable = false;

        // Call loadTable with updated status
        this.loadTable(1, 'id', 'asc');
        this.resetHeaders();
        this.updateStatusIndicator();
      });
    });
  }

  // Reset UI and accessibility
  resetHeaders() {
    this.tableHeaders.forEach(header => {
      // Unset sort UI in headers
      this.unsetHeader(header);
    });
    // Reset the announcement region
    this.tableAnnouncementRegion.innerHTML = '';
  }

  resetSearch() {
    this.searchInput.value = '';
    this.currentSearchTerm = '';
    hideElement(this.resetSearchButton);
    this.loadTable(1, 'id', 'asc');
    this.resetHeaders();
  }

  initializeResetSearchButton() {
    if (this.resetSearchButton) {
      this.resetSearchButton.addEventListener('click', () => {
        this.resetSearch();
      });
    }
  }

  resetFilters() {
    this.currentStatus = [];
    this.statusCheckboxes.forEach(checkbox => {
      checkbox.checked = false; 
    });
    hideElement(this.resetFiltersButton);

    // Disable the auto scroll
    this.scrollToTable = false;

    this.loadTable(1, 'id', 'asc');
    this.resetHeaders();
    this.updateStatusIndicator();
    // No need to toggle close the filters. The focus shift will trigger that for us.
  }

  initializeResetFiltersButton() {
    if (this.resetFiltersButton) {
      this.resetFiltersButton.addEventListener('click', () => {
        this.resetFilters();
      });
    }
  }

  updateStatusIndicator() {
    this.statusIndicator.innerHTML = '';
    // Even if the element is empty, it'll mess up the flex layout unless we set display none
    hideElement(this.statusIndicator);
    if (this.currentStatus.length)
      this.statusIndicator.innerHTML = '(' + this.currentStatus.length + ')';
      showElement(this.statusIndicator);
  }

  closeFilters() {
    if (this.statusToggle.getAttribute("aria-expanded") === "true") {
      this.statusToggle.click();
    }
  }

  initializeAccordionAccessibilityListeners() {
    // Instead of managing the toggle/close on the filter buttons in all edge cases (user clicks on search, user clicks on ANOTHER filter,
    // user clicks on main nav...) we add a listener and close the filters whenever the focus shifts out of the dropdown menu/filter button.
    // NOTE: We may need to evolve this as we add more filters.
    document.addEventListener('focusin', (event) => {
      const accordion = document.querySelector('.usa-accordion--select');
      const accordionThatIsOpen = document.querySelector('.usa-button--filter[aria-expanded="true"]');
      
      if (accordionThatIsOpen && !accordion.contains(event.target)) {
        this.closeFilters();
      }
    });

    // Close when user clicks outside
    // NOTE: We may need to evolve this as we add more filters.
    document.addEventListener('click', (event) => {
      const accordion = document.querySelector('.usa-accordion--select');
      const accordionThatIsOpen = document.querySelector('.usa-button--filter[aria-expanded="true"]');
    
      if (accordionThatIsOpen && !accordion.contains(event.target)) {
        this.closeFilters();
      }
    });
  }
}

class DomainsTable extends BaseTable {

  constructor() {
    super('domain');
  }
  getBaseUrl() {
    return document.getElementById("get_domains_json_url");
  }
  getDataObjects(data) {
    return data.domains;
  }
  addRow(dataObject, tbody, customTableOptions) {
    const domain = dataObject;
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    const expirationDate = domain.expiration_date ? new Date(domain.expiration_date) : null;
    const expirationDateFormatted = expirationDate ? expirationDate.toLocaleDateString('en-US', options) : '';
    const expirationDateSortValue = expirationDate ? expirationDate.getTime() : '';
    const actionUrl = domain.action_url;
    const suborganization = domain.domain_info__sub_organization ? domain.domain_info__sub_organization : '⎯';

    const row = document.createElement('tr');

    let markupForSuborganizationRow = '';

    if (this.portfolioValue) {
      markupForSuborganizationRow = `
        <td>
            <span class="text-wrap" aria-label="${domain.suborganization ? suborganization : 'No suborganization'}">${suborganization}</span>
        </td>
      `
    }

    row.innerHTML = `
      <th scope="row" role="rowheader" data-label="Domain name">
        ${domain.name}
      </th>
      <td data-sort-value="${expirationDateSortValue}" data-label="Expires">
        ${expirationDateFormatted}
      </td>
      <td data-label="Status">
        ${domain.state_display}
        <svg 
          class="usa-icon usa-tooltip usa-tooltip--registrar text-middle margin-bottom-05 text-accent-cool no-click-outline-and-cursor-help" 
          data-position="top"
          title="${domain.get_state_help_text}"
          focusable="true"
          aria-label="${domain.get_state_help_text}"
          role="tooltip"
        >
          <use aria-hidden="true" xlink:href="/public/img/sprite.svg#info_outline"></use>
        </svg>
      </td>
      ${markupForSuborganizationRow}
      <td>
        <a href="${actionUrl}">
          <svg class="usa-icon" aria-hidden="true" focusable="false" role="img" width="24">
            <use xlink:href="/public/img/sprite.svg#${domain.svg_icon}"></use>
          </svg>
          ${domain.action_label} <span class="usa-sr-only">${domain.name}</span>
        </a>
      </td>
    `;
    tbody.appendChild(row);
  }
}

class DomainRequestsTable extends BaseTable {

  constructor() {
    super('domain-request');
  }
  
  getBaseUrl() {
    return document.getElementById("get_domain_requests_json_url");
  }

  toggleExportButton(requests) {
    const exportButton = document.getElementById('export-csv'); 
    if (exportButton) {
        if (requests.length > 0) {
            showElement(exportButton);
        } else {
            hideElement(exportButton);
        }
    }
  }

  getDataObjects(data) {
    return data.domain_requests;
  }
  unloadModals() {
    uswdsUnloadModals();
  }
  customizeTable(data) {

    // Manage "export as CSV" visibility for domain requests
    this.toggleExportButton(data.domain_requests);

    let needsDeleteColumn = data.domain_requests.some(request => request.is_deletable);

    // Remove existing delete th and td if they exist
    let existingDeleteTh =  document.querySelector('.delete-header');
    if (!needsDeleteColumn) {
      if (existingDeleteTh)
        existingDeleteTh.remove();
    } else {
      if (!existingDeleteTh) {
        const delheader = document.createElement('th');
        delheader.setAttribute('scope', 'col');
        delheader.setAttribute('role', 'columnheader');
        delheader.setAttribute('class', 'delete-header width-5');
        delheader.innerHTML = `
          <span class="usa-sr-only">Delete Action</span>`;
        let tableHeaderRow = this.tableWrapper.querySelector('thead tr');
        tableHeaderRow.appendChild(delheader);
      }
    }
    return { 'needsAdditionalColumn': needsDeleteColumn };
  }

  addRow(dataObject, tbody, customTableOptions) {
    const request = dataObject;
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    const domainName = request.requested_domain ? request.requested_domain : `New domain request <br><span class="text-base font-body-xs">(${utcDateString(request.created_at)})</span>`;
    const actionUrl = request.action_url;
    const actionLabel = request.action_label;
    const submissionDate = request.last_submitted_date ? new Date(request.last_submitted_date).toLocaleDateString('en-US', options) : `<span class="text-base">Not submitted</span>`;
    
    // The markup for the delete function either be a simple trigger or a 3 dots menu with a hidden trigger (in the case of portfolio requests page)
    // If the request is not deletable, use the following (hidden) span for ANDI screenreaders to indicate this state to the end user
    let modalTrigger =  `
    <span class="usa-sr-only">Domain request cannot be deleted now. Edit the request for more information.</span>`;

    let markupCreatorRow = '';

    if (this.portfolioValue) {
      markupCreatorRow = `
        <td>
            <span class="text-wrap break-word">${request.creator ? request.creator : ''}</span>
        </td>
      `
    }

    if (request.is_deletable) {
      // 1st option: Just a modal trigger in any screen size for non-org users
      modalTrigger = `
        <a 
          role="button" 
          id="button-toggle-delete-domain-${request.id}"
          href="#toggle-delete-domain-${request.id}"
          class="usa-button text-secondary usa-button--unstyled text-no-underline late-loading-modal-trigger line-height-sans-5"
          aria-controls="toggle-delete-domain-${request.id}"
          data-open-modal
        >
          <svg class="usa-icon" aria-hidden="true" focusable="false" role="img" width="24">
            <use xlink:href="/public/img/sprite.svg#delete"></use>
          </svg> Delete <span class="usa-sr-only">${domainName}</span>
        </a>`

      // Request is deletable, modal and modalTrigger are built. Now check if we are on the portfolio requests page (by seeing if there is a portfolio value) and enhance the modalTrigger accordingly
      if (this.portfolioValue) {

        // 2nd option: Just a modal trigger on mobile for org users
        // 3rd option: kebab + accordion with nested modal trigger on desktop for org users
        modalTrigger = generateKebabHTML('delete-domain', request.id, 'Delete', domainName);
      }
    }

    const row = document.createElement('tr');
    row.innerHTML = `
      <th scope="row" role="rowheader" data-label="Domain name">
        ${domainName}
      </th>
      <td data-sort-value="${new Date(request.last_submitted_date).getTime()}" data-label="Date submitted">
        ${submissionDate}
      </td>
      ${markupCreatorRow}
      <td data-label="Status">
        ${request.status}
      </td>
      <td>
        <a href="${actionUrl}">
          <svg class="usa-icon" aria-hidden="true" focusable="false" role="img" width="24">
            <use xlink:href="/public/img/sprite.svg#${request.svg_icon}"></use>
          </svg>
          ${actionLabel} <span class="usa-sr-only">${request.requested_domain ? request.requested_domain : 'New domain request'}</span>
        </a>
      </td>
      ${customTableOptions.needsAdditionalColumn ? '<td>'+modalTrigger+'</td>' : ''}
    `;
    tbody.appendChild(row);
    if (request.is_deletable) DomainRequestsTable.addDomainRequestsModal(request.requested_domain, request.id, request.created_at, tbody);
  }

  initializeModals(page, total, unfiltered_total) {
    // initialize modals immediately after the DOM content is updated
    uswdsInitializeModals();

    // Now the DOM and modals are ready, add listeners to the submit buttons
    const modals = document.querySelectorAll('.usa-modal__content');

    modals.forEach(modal => {
      const submitButton = modal.querySelector('.usa-modal__submit');
      const closeButton = modal.querySelector('.usa-modal__close');
      submitButton.addEventListener('click', () => {
        let pk = submitButton.getAttribute('data-pk');
        // Close the modal to remove the USWDS UI local classes
        closeButton.click();
        // If we're deleting the last item on a page that is not page 1, we'll need to refresh the display to the previous page
        let pageToDisplay = page;
        if (total == 1 && unfiltered_total > 1) {
          pageToDisplay--;
        }
        this.deleteDomainRequest(pk, pageToDisplay);
      });
    });
  }

  /**
   * Delete is actually a POST API that requires a csrf token. The token will be waiting for us in the template as a hidden input.
   * @param {*} domainRequestPk - the identifier for the request that we're deleting
   * @param {*} pageToDisplay - If we're deleting the last item on a page that is not page 1, we'll need to display the previous page
  */
  deleteDomainRequest(domainRequestPk, pageToDisplay) {
    // Use to debug uswds modal issues
    //console.log('deleteDomainRequest')
    
    // Get csrf token
    const csrfToken = getCsrfToken();
    // Create FormData object and append the CSRF token
    const formData = `csrfmiddlewaretoken=${encodeURIComponent(csrfToken)}&delete-domain-request=`;

    fetch(`/domain-request/${domainRequestPk}/delete`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': csrfToken,
      },
      body: formData
    })
    .then(response => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      // Update data and UI
      this.loadTable(pageToDisplay, this.currentSortBy, this.currentOrder, this.scrollToTable, this.currentStatus, this.currentSearchTerm);
    })
    .catch(error => console.error('Error fetching domain requests:', error));
  }

  static addDomainRequestsModal(requested_domain, id, created_at, wrapper_element) {
    // If the request is deletable, create modal body and insert it. This is true for both requests and portfolio requests pages
    let modalHeading = '';
    let modalDescription = '';

    if (requested_domain) {
      modalHeading = `Are you sure you want to delete ${requested_domain}?`;
      modalDescription = 'This will remove the domain request from the .gov registrar. This action cannot be undone.';
    } else {
      if (request.created_at) {
        modalHeading = 'Are you sure you want to delete this domain request?';
        modalDescription = `This will remove the domain request (created ${utcDateString(created_at)}) from the .gov registrar. This action cannot be undone`;
      } else {
        modalHeading = 'Are you sure you want to delete New domain request?';
        modalDescription = 'This will remove the domain request from the .gov registrar. This action cannot be undone.';
      }
    }

    const modalSubmit = `
      <button type="button"
      class="usa-button usa-button--secondary usa-modal__submit"
      data-pk = ${id}
      name="delete-domain-request">Yes, delete request</button>
    `

    addModal('toggle-delete-domain', id, 'Are you sure you want to continue?', 'Domain will be removed', modalHeading, modalDescription, modalSubmit, wrapper_element, true);

  }
}

class MembersTable extends BaseTable {

  constructor() {
    super('member');
  }
  
  getBaseUrl() {
    return document.getElementById("get_members_json_url");
  }

  // Abstract method (to be implemented in the child class)
  getDataObjects(data) {
    return data.members;
  }
  unloadModals() {
    uswdsUnloadModals();
  }
  initializeModals(page, total, unfiltered_total) {
    // initialize modals immediately after the DOM content is updated
    uswdsInitializeModals();

    // Now the DOM and modals are ready, add listeners to the submit buttons
    const modals = document.querySelectorAll('.usa-modal__content');

    modals.forEach(modal => {
      const submitButton = modal.querySelector('.usa-modal__submit');
      const closeButton = modal.querySelector('.usa-modal__close');
      submitButton.addEventListener('click', () => {
        let pk = submitButton.getAttribute('data-pk');
        // Close the modal to remove the USWDS UI local classes
        closeButton.click();
        // If we're deleting the last item on a page that is not page 1, we'll need to refresh the display to the previous page
        let pageToDisplay = page;
        if (total == 1 && unfiltered_total > 1) {
          pageToDisplay--;
        }

        this.deleteMember(pk, pageToDisplay);
      });
    });
  }

  customizeTable(data) {
    // Get whether the logged in user has edit members permission
    const hasEditPermission = this.portfolioElement ? this.portfolioElement.getAttribute('data-has-edit-permission')==='True' : null;

    let existingExtraActionsHeader =  document.querySelector('.extra-actions-header');

    if (hasEditPermission && !existingExtraActionsHeader) {
      const extraActionsHeader = document.createElement('th');
      extraActionsHeader.setAttribute('id', 'extra-actions');
      extraActionsHeader.setAttribute('role', 'columnheader');
      extraActionsHeader.setAttribute('class', 'extra-actions-header width-5');
      extraActionsHeader.innerHTML = `
        <span class="usa-sr-only">Extra Actions</span>`;
      let tableHeaderRow = this.tableWrapper.querySelector('thead tr');
      tableHeaderRow.appendChild(extraActionsHeader);
    }
    return { 
      'needsAdditionalColumn': hasEditPermission,
      'UserPortfolioPermissionChoices' : data.UserPortfolioPermissionChoices
    };
  }

  addRow(dataObject, tbody, customTableOptions) {
    const member = dataObject;
    // member is based on either a UserPortfolioPermission or a PortfolioInvitation
    // and also includes information from related domains; the 'id' of the org_member
    // is the id of the UserPorfolioPermission or PortfolioInvitation, it is not a user id
    // member.type is either invitedmember or member
    const unique_id = member.type + member.id; // unique string for use in dom, this is
    // not the id of the associated user
    const member_delete_url = member.action_url + "/delete";
    const num_domains = member.domain_urls.length;
    const last_active = this.handleLastActive(member.last_active);
    let cancelInvitationButton = member.type === "invitedmember" ? "Cancel invitation" : "Remove member";
    const kebabHTML = customTableOptions.needsAdditionalColumn ? generateKebabHTML('remove-member', unique_id, cancelInvitationButton, `for ${member.name}`): ''; 
          
    const row = document.createElement('tr');
    
    let admin_tagHTML = ``;
    if (member.is_admin)
      admin_tagHTML = `<span class="usa-tag margin-left-1 bg-primary">Admin</span>`

    // generate html blocks for domains and permissions for the member
    let domainsHTML = this.generateDomainsHTML(num_domains, member.domain_names, member.domain_urls, member.action_url);
    let permissionsHTML = this.generatePermissionsHTML(member.permissions, customTableOptions.UserPortfolioPermissionChoices);
    
    // domainsHTML block and permissionsHTML block need to be wrapped with hide/show toggle, Expand
    let showMoreButton = '';
    const showMoreRow = document.createElement('tr');
    if (domainsHTML || permissionsHTML) {
      showMoreButton = `
        <button 
          type="button" 
          class="usa-button--show-more-button usa-button usa-button--unstyled display-block margin-top-1" 
          data-for=${unique_id}
          aria-label="Expand for additional information"
        >
          <span>Expand</span>
          <svg class="usa-icon usa-icon--big" aria-hidden="true" focusable="false" role="img" width="24">
            <use xlink:href="/public/img/sprite.svg#expand_more"></use>
          </svg>
        </button>
      `;

      showMoreRow.innerHTML = `<td colspan='3' headers="header-member row-header-${unique_id}" class="padding-top-0"><div class='grid-row'>${domainsHTML} ${permissionsHTML}</div></td>`;
      showMoreRow.classList.add('show-more-content');
      showMoreRow.classList.add('display-none');
      showMoreRow.id = unique_id;
    }

    row.innerHTML = `
      <th role="rowheader" headers="header-member" data-label="member email" id='row-header-${unique_id}'>
        ${member.member_display} ${admin_tagHTML} ${showMoreButton}
      </th>
      <td headers="header-last-active row-header-${unique_id}" data-sort-value="${last_active.sort_value}" data-label="last_active">
        ${last_active.display_value}
      </td>
      <td headers="header-action row-header-${unique_id}">
        <a href="${member.action_url}">
          <svg class="usa-icon" aria-hidden="true" focusable="false" role="img" width="24">
            <use xlink:href="/public/img/sprite.svg#${member.svg_icon}"></use>
          </svg>
          ${member.action_label} <span class="usa-sr-only">${member.name}</span>
        </a>
      </td>
      ${customTableOptions.needsAdditionalColumn ? '<td>'+kebabHTML+'</td>' : ''}
    `;
    tbody.appendChild(row);
    if (domainsHTML || permissionsHTML) {
      tbody.appendChild(showMoreRow);
    }
    // This easter egg is only for fixtures that dont have names as we are displaying their emails
    // All prod users will have emails linked to their account
    if (customTableOptions.needsAdditionalColumn) MembersTable.addMemberModal(num_domains, member.email || "Samwise Gamgee", member_delete_url, unique_id, row);
  }

  /**
   * Initializes "Show More" buttons on the page, enabling toggle functionality to show or hide content.
   * 
   * The function finds elements with "Show More" buttons and sets up a click event listener to toggle the visibility
   * of a corresponding content div. When clicked, the button updates its visual state (e.g., text/icon change),
   * and the associated content is shown or hidden based on its current visibility status.
   *
   * @function initShowMoreButtons
   */
  initShowMoreButtons() {
    /**
     * Toggles the visibility of a content section when the "Show More" button is clicked.
     * Updates the button text/icon based on whether the content is shown or hidden.
     *
     * @param {HTMLElement} toggleButton - The button that toggles the content visibility.
     * @param {HTMLElement} contentDiv - The content div whose visibility is toggled.
     * @param {HTMLElement} buttonParentRow - The parent row element containing the button.
     */
    function toggleShowMoreButton(toggleButton, contentDiv, buttonParentRow) {
      const spanElement = toggleButton.querySelector('span');
      const useElement = toggleButton.querySelector('use');
      if (contentDiv.classList.contains('display-none')) {
        showElement(contentDiv);
        spanElement.textContent = 'Close';
        useElement.setAttribute('xlink:href', '/public/img/sprite.svg#expand_less');
        buttonParentRow.classList.add('hide-td-borders');
        toggleButton.setAttribute('aria-label', 'Close additional information');
      } else {    
        hideElement(contentDiv);
        spanElement.textContent = 'Expand';
        useElement.setAttribute('xlink:href', '/public/img/sprite.svg#expand_more');
        buttonParentRow.classList.remove('hide-td-borders');
        toggleButton.setAttribute('aria-label', 'Expand for additional information');
      }
    }
  
    let toggleButtons = document.querySelectorAll('.usa-button--show-more-button');
    toggleButtons.forEach((toggleButton) => {
      
      // get contentDiv for element specified in data-for attribute of toggleButton
      let dataFor = toggleButton.dataset.for;
      let contentDiv = document.getElementById(dataFor);
      let buttonParentRow = toggleButton.parentElement.parentElement;
      if (contentDiv && contentDiv.tagName.toLowerCase() === 'tr' && contentDiv.classList.contains('show-more-content') && buttonParentRow && buttonParentRow.tagName.toLowerCase() === 'tr') {
        toggleButton.addEventListener('click', function() {
          toggleShowMoreButton(toggleButton, contentDiv, buttonParentRow);
        });
      } else {
        console.warn('Found a toggle button with no associated toggleable content or parent row');
      }

    });
  }

  /**
   * Converts a given `last_active` value into a display value and a numeric sort value.
   * The input can be a UTC date, the strings "Invited", "Invalid date", or null/undefined.
   * 
   * @param {string} last_active - UTC date string or special status like "Invited" or "Invalid date".
   * @returns {Object} - An object containing `display_value` (formatted date or status string) 
   *                     and `sort_value` (numeric value for sorting).
   */
  handleLastActive(last_active) {
    const invited = 'Invited';
    const invalid_date = 'Invalid date';
    const options = { year: 'numeric', month: 'long', day: 'numeric' }; // Date display format

    let display_value = invalid_date; // Default display value for invalid or null dates
    let sort_value = -1;              // Default sort value for invalid or null dates

    if (last_active === invited) {
      // Handle "Invited" status: special case with 0 sort value
      display_value = invited;
      sort_value = 0;
    } else if (last_active && last_active !== invalid_date) {
      // Parse and format valid UTC date strings
      const parsedDate = new Date(last_active);

      if (!isNaN(parsedDate.getTime())) {
        // Valid date
        display_value = parsedDate.toLocaleDateString('en-US', options);
        sort_value = parsedDate.getTime(); // Use timestamp for sorting
      } else {
        console.error(`Error: Invalid date string provided: ${last_active}`);
      }
    }

    return { display_value, sort_value };
  }

  /**
   * Generates HTML for the list of domains assigned to a member.
   * 
   * @param {number} num_domains - The number of domains the member is assigned to.
   * @param {Array} domain_names - An array of domain names.
   * @param {Array} domain_urls - An array of corresponding domain URLs.
   * @returns {string} - A string of HTML displaying the domains assigned to the member.
   */
  generateDomainsHTML(num_domains, domain_names, domain_urls, action_url) {
    // Initialize an empty string for the HTML
    let domainsHTML = '';

    // Only generate HTML if the member has one or more assigned domains
    if (num_domains > 0) {
      domainsHTML += "<div class='desktop:grid-col-5 margin-bottom-2 desktop:margin-bottom-0'>";
      domainsHTML += "<h4 class='margin-y-0 text-primary'>Domains assigned</h4>";
      domainsHTML += `<p class='margin-y-0'>This member is assigned to ${num_domains} domains:</p>`;
      domainsHTML += "<ul class='usa-list usa-list--unstyled margin-y-0'>";

      // Display up to 6 domains with their URLs
      for (let i = 0; i < num_domains && i < 6; i++) {
        domainsHTML += `<li><a href="${domain_urls[i]}">${domain_names[i]}</a></li>`;
      }

      domainsHTML += "</ul>";

      // If there are more than 6 domains, display a "View assigned domains" link
      if (num_domains >= 6) {
        domainsHTML += `<p><a href="${action_url}/domains">View assigned domains</a></p>`;
      }

      domainsHTML += "</div>";
    }

    return domainsHTML;
  }

  deleteMember(member_delete_url, pageToDisplay) {
    // Get csrf token
    const csrfToken = getCsrfToken();
    // Create FormData object and append the CSRF token
    const formData = `csrfmiddlewaretoken=${encodeURIComponent(csrfToken)}`;
  
    fetch(`${member_delete_url}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': csrfToken,
      },
      body: formData
    })
    .then(response => {
      if (response.status === 200) {
        response.json().then(data => {
          if (data.success) {
            this.addAlert("success", data.success);
          }
          this.loadTable(pageToDisplay, this.currentSortBy, this.currentOrder, this.scrollToTable, this.currentStatus, this.currentSearchTerm);
        });
      } else {
        // If the response isn't 204, handle the error response
        response.json().then(data => {
          if (data.error) {
            // This should display the error given from backend for
            // either only admin OR in progress requests
            this.addAlert("error", data.error); 
          } else {
            throw new Error(`Unexpected status: ${response.status}`);
          }
        });
      }
    })
    .catch(error => {
      console.error('Error deleting member:', error);
    });
  }
  
  
  /**
   * Adds an alert message to the page with an alert class.
   *
   * @param {string} alertClass - {error, warning, info, success}
   * @param {string} alertMessage - The text that will be displayed
   *
   */
  addAlert(alertClass, alertMessage) {
    let toggleableAlertDiv = document.getElementById("toggleable-alert");
    this.resetAlerts();
    toggleableAlertDiv.classList.add(`usa-alert--${alertClass}`);
    let alertParagraph = toggleableAlertDiv.querySelector(".usa-alert__text");
    alertParagraph.innerHTML = alertMessage
    showElement(toggleableAlertDiv);
  }
  
  /**
   * Resets the reusable alert message
   */
  resetAlerts() {
    // Create a list of any alert that's leftover and remove
    document.querySelectorAll(".usa-alert:not(#toggleable-alert)").forEach(alert => {
      alert.remove();
    });
    let toggleableAlertDiv = document.getElementById("toggleable-alert");
    toggleableAlertDiv.classList.remove('usa-alert--error');
    toggleableAlertDiv.classList.remove('usa-alert--success');
    hideElement(toggleableAlertDiv);
  }

  /**
   * Generates an HTML string summarizing a user's additional permissions within a portfolio, 
   * based on the user's permissions and predefined permission choices.
   *
   * @param {Array} member_permissions - An array of permission strings that the member has.
   * @param {Object} UserPortfolioPermissionChoices - An object containing predefined permission choice constants.
   *        Expected keys include:
   *        - VIEW_ALL_DOMAINS
   *        - VIEW_MANAGED_DOMAINS
   *        - EDIT_REQUESTS
   *        - VIEW_ALL_REQUESTS
   *        - EDIT_MEMBERS
   *        - VIEW_MEMBERS
   * 
   * @returns {string} - A string of HTML representing the user's additional permissions.
   *                     If the user has no specific permissions, it returns a default message
   *                     indicating no additional permissions.
   *
   * Behavior:
   * - The function checks the user's permissions (`member_permissions`) and generates
   *   corresponding HTML sections based on the permission choices defined in `UserPortfolioPermissionChoices`.
   * - Permissions are categorized into domains, requests, and members:
   *   - Domains: Determines whether the user can view or manage all or assigned domains.
   *   - Requests: Differentiates between users who can edit requests, view all requests, or have no request privileges.
   *   - Members: Distinguishes between members who can manage or only view other members.
   * - If no relevant permissions are found, the function returns a message stating that the user has no additional permissions.
   * - The resulting HTML always includes a header "Additional permissions for this member" and appends the relevant permission descriptions.
   */
  generatePermissionsHTML(member_permissions, UserPortfolioPermissionChoices) {
    let permissionsHTML = '';

    // Check domain-related permissions
    if (member_permissions.includes(UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS)) {
      permissionsHTML += "<p class='margin-top-1 p--blockquote'><strong class='text-base-dark'>Domains:</strong> Can view all organization domains. Can manage domains they are assigned to and edit information about the domain (including DNS settings).</p>";
    } else if (member_permissions.includes(UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS)) {
      permissionsHTML += "<p class='margin-top-1 p--blockquote'><strong class='text-base-dark'>Domains:</strong> Can manage domains they are assigned to and edit information about the domain (including DNS settings).</p>";
    }

    // Check request-related permissions
    if (member_permissions.includes(UserPortfolioPermissionChoices.EDIT_REQUESTS)) {
      permissionsHTML += "<p class='margin-top-1 p--blockquote'><strong class='text-base-dark'>Domain requests:</strong> Can view all organization domain requests. Can create domain requests and modify their own requests.</p>";
    } else if (member_permissions.includes(UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS)) {
      permissionsHTML += "<p class='margin-top-1 p--blockquote'><strong class='text-base-dark'>Domain requests (view-only):</strong> Can view all organization domain requests. Can't create or modify any domain requests.</p>";
    }

    // Check member-related permissions
    if (member_permissions.includes(UserPortfolioPermissionChoices.EDIT_MEMBERS)) {
      permissionsHTML += "<p class='margin-top-1 p--blockquote'><strong class='text-base-dark'>Members:</strong> Can manage members including inviting new members, removing current members, and assigning domains to members.</p>";
    } else if (member_permissions.includes(UserPortfolioPermissionChoices.VIEW_MEMBERS)) {
      permissionsHTML += "<p class='margin-top-1 p--blockquote'><strong class='text-base-dark'>Members (view-only):</strong> Can view all organizational members. Can't manage any members.</p>";
    }

    // If no specific permissions are assigned, display a message indicating no additional permissions
    if (!permissionsHTML) {
      permissionsHTML += "<p class='margin-top-1 p--blockquote'><b>No additional permissions:</b> There are no additional permissions for this member.</p>";
    }

    // Add a permissions header and wrap the entire output in a container
    permissionsHTML = "<div class='desktop:grid-col-7'><h4 class='margin-y-0 text-primary'>Additional permissions for this member</h4>" + permissionsHTML + "</div>";
    
    return permissionsHTML;
  }

  static addMemberModal(num_domains, member_email, submit_delete_url, id, wrapper_element) {
    let modalHeading = '';
    let modalDescription = '';
    
    if (num_domains == 0){
      modalHeading = `Are you sure you want to delete ${member_email}?`;
      modalDescription = `They will no longer be able to access this organization. 
      This action cannot be undone.`;
    } else if (num_domains == 1) {
      modalHeading = `Are you sure you want to delete ${member_email}?`;
      modalDescription = `<b>${member_email}</b> currently manages ${num_domains} domain in the organization.
      Removing them from the organization will remove all of their domains. They will no longer be able to
      access this organization. This action cannot be undone.`;
    } else if (num_domains >= 1) {
      modalHeading = `Are you sure you want to delete ${member_email}?`;
      modalDescription = `<b>${member_email}</b> currently manages ${num_domains} domains in the organization.
      Removing them from the organization will remove all of their domains. They will no longer be able to
      access this organization. This action cannot be undone.`;
    }

    const modalSubmit = `
      <button type="button"
      class="usa-button usa-button--secondary usa-modal__submit"
      data-pk = ${submit_delete_url}
      name="delete-member">Yes, remove from organization</button>
    `

    addModal('toggle-remove-member', id, 'Are you sure you want to continue?', 'Member will be removed', modalHeading, modalDescription, modalSubmit, wrapper_element, true);
  }

  
}

class MemberDomainsTable extends BaseTable {

  constructor() {
    super('member-domain');
    this.currentSortBy = 'name';
  }
  getBaseUrl() {
    return document.getElementById("get_member_domains_json_url");
  }
  getDataObjects(data) {
    return data.domains;
  }
  addRow(dataObject, tbody, customTableOptions) {
    const domain = dataObject;
    const row = document.createElement('tr');

    row.innerHTML = `
      <td scope="row" data-label="Domain name">
        ${domain.name}
      </td>
    `;
    tbody.appendChild(row);
  }

}


/**
 * An IIFE that listens for DOM Content to be loaded, then executes.  This function
 * initializes the domains list and associated functionality.
 *
 */
document.addEventListener('DOMContentLoaded', function() {
  const isDomainsPage = document.getElementById("domains") 
  if (isDomainsPage){
    const domainsTable = new DomainsTable();
    if (domainsTable.tableWrapper) {
      // Initial load
      domainsTable.loadTable(1);
    }
  }
});

/**
 * An IIFE that listens for DOM Content to be loaded, then executes. This function
 * initializes the domain requests list and associated functionality.
 *
 */
document.addEventListener('DOMContentLoaded', function() {
  const domainRequestsSectionWrapper = document.getElementById('domain-requests');
  if (domainRequestsSectionWrapper) {
    const domainRequestsTable = new DomainRequestsTable();
    if (domainRequestsTable.tableWrapper) {
      domainRequestsTable.loadTable(1);
    }
  }

  document.addEventListener('focusin', function(event) {
    closeOpenAccordions(event);
  });
  
  document.addEventListener('click', function(event) {
    closeOpenAccordions(event);
  });

  function closeMoreActionMenu(accordionThatIsOpen) {
    if (accordionThatIsOpen.getAttribute("aria-expanded") === "true") {
      accordionThatIsOpen.click();
    }
  }

  function closeOpenAccordions(event) {
    const openAccordions = document.querySelectorAll('.usa-button--more-actions[aria-expanded="true"]');
    openAccordions.forEach((openAccordionButton) => {
      // Find the corresponding accordion
      const accordion = openAccordionButton.closest('.usa-accordion--more-actions');
      if (accordion && !accordion.contains(event.target)) {
        // Close the accordion if the click is outside
        closeMoreActionMenu(openAccordionButton);
      }
    });
  }
});

const utcDateString = (dateString) => {
  const date = new Date(dateString);
  const utcYear = date.getUTCFullYear();
  const utcMonth = date.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' });
  const utcDay = date.getUTCDate().toString().padStart(2, '0');
  let utcHours = date.getUTCHours();
  const utcMinutes = date.getUTCMinutes().toString().padStart(2, '0');

  const ampm = utcHours >= 12 ? 'PM' : 'AM';
  utcHours = utcHours % 12 || 12;  // Convert to 12-hour format, '0' hours should be '12'

  return `${utcMonth} ${utcDay}, ${utcYear}, ${utcHours}:${utcMinutes} ${ampm} UTC`;
};



/**
 * An IIFE that listens for DOM Content to be loaded, then executes.  This function
 * initializes the members list and associated functionality.
 *
 */
document.addEventListener('DOMContentLoaded', function() {
  const isMembersPage = document.getElementById("members") 
  if (isMembersPage){
    const membersTable = new MembersTable();
    if (membersTable.tableWrapper) {
      // Initial load
      membersTable.loadTable(1);
    }
  }
});

/**
 * An IIFE that listens for DOM Content to be loaded, then executes.  This function
 * initializes the member domains list and associated functionality.
 *
 */
document.addEventListener('DOMContentLoaded', function() {
  const isMemberDomainsPage = document.getElementById("member-domains") 
  if (isMemberDomainsPage){
    const memberDomainsTable = new MemberDomainsTable();
    if (memberDomainsTable.tableWrapper) {
      // Initial load
      memberDomainsTable.loadTable(1);
    }
  }
});

/**
 * An IIFE that displays confirmation modal on the user profile page
 */
(function userProfileListener() {

  const showConfirmationModalTrigger = document.querySelector('.show-confirmation-modal');
  if (showConfirmationModalTrigger) {
    showConfirmationModalTrigger.click();
  }
}
)();

/**
 * An IIFE that hooks up the edit buttons on the finish-user-setup page
 */
(function finishUserSetupListener() {

  function getInputField(fieldName){
    return document.querySelector(`#id_${fieldName}`)
  }

  // Shows the hidden input field and hides the readonly one
  function showInputFieldHideReadonlyField(fieldName, button) {
    let inputField = getInputField(fieldName)
    let readonlyField = document.querySelector(`#${fieldName}__edit-button-readonly`)

    readonlyField.classList.toggle('display-none');
    inputField.classList.toggle('display-none');

    // Toggle the bold style on the grid row
    let gridRow = button.closest(".grid-col-2").closest(".grid-row")
    if (gridRow){
      gridRow.classList.toggle("bold-usa-label")
    }
  }

  function handleFullNameField(fieldName = "full_name") {
    // Remove the display-none class from the nearest parent div
    let nameFieldset = document.querySelector("#profile-name-group");
    if (nameFieldset){
      nameFieldset.classList.remove("display-none");
    }

    // Hide the "full_name" field
    let inputField = getInputField(fieldName);
    if (inputField) {
      inputFieldParentDiv = inputField.closest("div");
      if (inputFieldParentDiv) {
        inputFieldParentDiv.classList.add("display-none");
      }
    }
  }

  function handleEditButtonClick(fieldName, button){
    button.addEventListener('click', function() {
      // Lock the edit button while this operation occurs
      button.disabled = true

      if (fieldName == "full_name"){
        handleFullNameField();
      }else {
        showInputFieldHideReadonlyField(fieldName, button);
      }
      
      // Hide the button itself
      button.classList.add("display-none");

      // Unlock after it completes
      button.disabled = false
    });
  }

  function setupListener(){

    

    document.querySelectorAll('[id$="__edit-button"]').forEach(function(button) {
      // Get the "{field_name}" and "edit-button"
      let fieldIdParts = button.id.split("__")
      if (fieldIdParts && fieldIdParts.length > 0){
        let fieldName = fieldIdParts[0]
        
        // When the edit button is clicked, show the input field under it
        handleEditButtonClick(fieldName, button);

        let editableFormGroup = button.parentElement.parentElement.parentElement;
        if (editableFormGroup){
          let readonlyField = editableFormGroup.querySelector(".toggleable_input__readonly-field")
          let inputField = document.getElementById(`id_${fieldName}`);
          if (!inputField || !readonlyField) {
            return;
          }

          let inputFieldValue = inputField.value
          if (inputFieldValue || fieldName == "full_name"){
            if (fieldName == "full_name"){
              let firstName = document.querySelector("#id_first_name");
              let middleName = document.querySelector("#id_middle_name");
              let lastName = document.querySelector("#id_last_name");
              if (firstName && lastName && firstName.value && lastName.value) {
                let values = [firstName.value, middleName.value, lastName.value]
                readonlyField.innerHTML = values.join(" ");
              }else {
                let fullNameField = document.querySelector('#full_name__edit-button-readonly');
                let svg = fullNameField.querySelector("svg use")
                if (svg) {
                  const currentHref = svg.getAttribute('xlink:href');
                  if (currentHref) {
                    const parts = currentHref.split('#');
                    if (parts.length === 2) {
                      // Keep the path before '#' and replace the part after '#' with 'invalid'
                      const newHref = parts[0] + '#error';
                      svg.setAttribute('xlink:href', newHref);
                      fullNameField.classList.add("toggleable_input__error")
                      label = fullNameField.querySelector(".toggleable_input__readonly-field")
                      label.innerHTML = "Unknown";
                    }
                  }
                }
              }
              
              // Technically, the full_name field is optional, but we want to display it as required. 
              // This style is applied to readonly fields (gray text). This just removes it, as
              // this is difficult to achieve otherwise by modifying the .readonly property.
              if (readonlyField.classList.contains("text-base")) {
                readonlyField.classList.remove("text-base")
              }
            }else {
              readonlyField.innerHTML = inputFieldValue
            }
          }
        }
      }
    });
  }

  function showInputOnErrorFields(){
    document.addEventListener('DOMContentLoaded', function() {

      // Get all input elements within the form
      let form = document.querySelector("#finish-profile-setup-form");
      let inputs = form ? form.querySelectorAll("input") : null;
      if (!inputs) {
        return null;
      }

      let fullNameButtonClicked = false
      inputs.forEach(function(input) {
        let fieldName = input.name;
        let errorMessage = document.querySelector(`#id_${fieldName}__error-message`);

        // If no error message is found, do nothing
        if (!fieldName || !errorMessage) {
          return null;
        }

        let editButton = document.querySelector(`#${fieldName}__edit-button`);
        if (editButton){
          // Show the input field of the field that errored out 
          editButton.click();
        }

        // If either the full_name field errors out,
        // or if any of its associated fields do - show all name related fields.
        let nameFields = ["first_name", "middle_name", "last_name"];
        if (nameFields.includes(fieldName) && !fullNameButtonClicked){
          // Click the full name button if any of its related fields error out
          fullNameButton = document.querySelector("#full_name__edit-button");
          if (fullNameButton) {
            fullNameButton.click();
            fullNameButtonClicked = true;
          }
        }
      });  
    });
  };

  setupListener();

  // Show the input fields if an error exists
  showInputOnErrorFields();

})();


/**
 * An IIFE that changes the default clear behavior on comboboxes to the input field.
 * We want the search bar to act soley as a search bar.
 */
(function loadInitialValuesForComboBoxes() {
  var overrideDefaultClearButton = true;
  var isTyping = false;

  document.addEventListener('DOMContentLoaded', (event) => {
    handleAllComboBoxElements();
  });

  function handleAllComboBoxElements() {
    const comboBoxElements = document.querySelectorAll(".usa-combo-box");
    comboBoxElements.forEach(comboBox => {
      const input = comboBox.querySelector("input");
      const select = comboBox.querySelector("select");
      if (!input || !select) {
        console.warn("No combobox element found");
        return;
      }
      // Set the initial value of the combobox
      let initialValue = select.getAttribute("data-default-value");
      let clearInputButton = comboBox.querySelector(".usa-combo-box__clear-input");
      if (!clearInputButton) {
        console.warn("No clear element found");
        return;
      }

      // Override the default clear button behavior such that it no longer clears the input,
      // it just resets to the data-initial-value.

      // Due to the nature of how uswds works, this is slightly hacky.

      // Use a MutationObserver to watch for changes in the dropdown list
      const dropdownList = comboBox.querySelector(`#${input.id}--list`);
      const observer = new MutationObserver(function(mutations) {
          mutations.forEach(function(mutation) {
              if (mutation.type === "childList") {
                addBlankOption(clearInputButton, dropdownList, initialValue);
              }
          });
      });

      // Configure the observer to watch for changes in the dropdown list
      const config = { childList: true, subtree: true };
      observer.observe(dropdownList, config);

      // Input event listener to detect typing
      input.addEventListener("input", () => {
        isTyping = true;
      });

      // Blur event listener to reset typing state
      input.addEventListener("blur", () => {
        isTyping = false;
      });

      // Hide the reset button when there is nothing to reset.
      // Do this once on init, then everytime a change occurs.
      updateClearButtonVisibility(select, initialValue, clearInputButton)
      select.addEventListener("change", () => {
        updateClearButtonVisibility(select, initialValue, clearInputButton)
      });

      // Change the default input behaviour - have it reset to the data default instead
      clearInputButton.addEventListener("click", (e) => {
        if (overrideDefaultClearButton && initialValue) {
          e.preventDefault();
          e.stopPropagation();
          input.click();
          // Find the dropdown option with the desired value
          const dropdownOptions = document.querySelectorAll(".usa-combo-box__list-option");
          if (dropdownOptions) {
            dropdownOptions.forEach(option => {
                if (option.getAttribute("data-value") === initialValue) {
                    // Simulate a click event on the dropdown option
                    option.click();
                }
            });
          }
        }
      });
    });
  }

  function updateClearButtonVisibility(select, initialValue, clearInputButton) {
    if (select.value === initialValue) {
      hideElement(clearInputButton);
    }else {
      showElement(clearInputButton)
    }
  }

  function addBlankOption(clearInputButton, dropdownList, initialValue) {
    if (dropdownList && !dropdownList.querySelector('[data-value=""]') && !isTyping) {
        const blankOption = document.createElement("li");
        blankOption.setAttribute("role", "option");
        blankOption.setAttribute("data-value", "");
        blankOption.classList.add("usa-combo-box__list-option");
        if (!initialValue){
          blankOption.classList.add("usa-combo-box__list-option--selected")
        }
        blankOption.textContent = "⎯";

        dropdownList.insertBefore(blankOption, dropdownList.firstChild);
        blankOption.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          overrideDefaultClearButton = false;
          // Trigger the default clear behavior
          clearInputButton.click();
          overrideDefaultClearButton = true;
        });
    }
  }
})();

document.addEventListener("DOMContentLoaded", () => {
  (function portfolioMemberPageToggle() {
    const wrapperDeleteAction = document.getElementById("wrapper-delete-action")
    if (wrapperDeleteAction) {
        const member_type = wrapperDeleteAction.getAttribute("data-member-type");
        const member_id = wrapperDeleteAction.getAttribute("data-member-id");
        const num_domains = wrapperDeleteAction.getAttribute("data-num-domains");
        const member_name = wrapperDeleteAction.getAttribute("data-member-name");
        const member_email = wrapperDeleteAction.getAttribute("data-member-email"); 
        const member_delete_url = `${member_type}-${member_id}/delete`;
        const unique_id = `${member_type}-${member_id}`;

        let cancelInvitationButton = member_type === "invitedmember" ? "Cancel invitation" : "Remove member";
        wrapperDeleteAction.innerHTML = generateKebabHTML('remove-member', unique_id, cancelInvitationButton, `for ${member_name}`);

        // This easter egg is only for fixtures that dont have names as we are displaying their emails
        // All prod users will have emails linked to their account
        MembersTable.addMemberModal(num_domains, member_email || "Samwise Gamgee", member_delete_url, unique_id, wrapperDeleteAction);

        uswdsInitializeModals();

        // Now the DOM and modals are ready, add listeners to the submit buttons
        const modals = document.querySelectorAll('.usa-modal__content');

        modals.forEach(modal => {
          const submitButton = modal.querySelector('.usa-modal__submit');
          const closeButton = modal.querySelector('.usa-modal__close');
          submitButton.addEventListener('click', () => {
            closeButton.click();
            let delete_member_form = document.getElementById("member-delete-form");
            if (delete_member_form) {
              delete_member_form.submit();
            }
          });
        });
    }
  })();
});