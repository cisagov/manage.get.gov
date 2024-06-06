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
 * DOM elements with modal classes, unloadModals needs to be called before initializeModals.
 * 
 */
function initializeModals() {
  window.modal.on();
}

/**
 * Unload existing USWDS modals by calling off method.  Requires that uswds-edited.js be
 * loaded before get-gov.js.  uswds-edited.js adds the modal module to the window to be
 * accessible directly in get-gov.js.
 * See note above with regards to calling this method relative to initializeModals.
 * 
 */
function unloadModals() {
  window.modal.off();
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
    console.log('Error: unknown attribute name provided.');
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

/**
 * Generalized function to update pagination for a list.
 * @param {string} itemName - The name displayed in the counter
 * @param {string} paginationSelector - CSS selector for the pagination container.
 * @param {string} counterSelector - CSS selector for the pagination counter.
 * @param {string} headerAnchor - CSS selector for the header element to anchor the links to.
 * @param {Function} loadPageFunction - Function to call when a page link is clicked.
 * @param {number} currentPage - The current page number (starting with 1).
 * @param {number} numPages - The total number of pages.
 * @param {boolean} hasPrevious - Whether there is a page before the current page.
 * @param {boolean} hasNext - Whether there is a page after the current page.
 * @param {number} totalItems - The total number of items.
 * @param {string} searchTerm - The search term
 */
function updatePagination(itemName, paginationSelector, counterSelector, headerAnchor, loadPageFunction, currentPage, numPages, hasPrevious, hasNext, totalItems, searchTerm) {
  const paginationContainer = document.querySelector(paginationSelector);
  const paginationCounter = document.querySelector(counterSelector);
  const paginationButtons = document.querySelector(`${paginationSelector} .usa-pagination__list`);
  paginationCounter.innerHTML = '';
  paginationButtons.innerHTML = '';

  // Buttons should only be displayed if there are more than one pages of results
  paginationButtons.classList.toggle('display-none', numPages <= 1);

  // Counter should only be displayed if there is more than 1 item
  paginationContainer.classList.toggle('display-none', totalItems < 1);

  paginationCounter.innerHTML = `${totalItems} ${itemName}${totalItems > 1 ? 's' : ''}${searchTerm ? ' for ' + '"' + searchTerm + '"' : ''}`;

  if (hasPrevious) {
    const prevPageItem = document.createElement('li');
    prevPageItem.className = 'usa-pagination__item usa-pagination__arrow';
    prevPageItem.innerHTML = `
      <a href="${headerAnchor}" class="usa-pagination__link usa-pagination__previous-page" aria-label="Previous page">
        <svg class="usa-icon" aria-hidden="true" role="img">
          <use xlink:href="/public/img/sprite.svg#navigate_before"></use>
        </svg>
        <span class="usa-pagination__link-text">Previous</span>
      </a>
    `;
    prevPageItem.querySelector('a').addEventListener('click', (event) => {
      event.preventDefault();
      loadPageFunction(currentPage - 1);
    });
    paginationButtons.appendChild(prevPageItem);
  }

  // Helper function to create a page item
  function createPageItem(page) {
    const pageItem = document.createElement('li');
    pageItem.className = 'usa-pagination__item usa-pagination__page-no';
    pageItem.innerHTML = `
      <a href="${headerAnchor}" class="usa-pagination__button" aria-label="Page ${page}">${page}</a>
    `;
    if (page === currentPage) {
      pageItem.querySelector('a').classList.add('usa-current');
      pageItem.querySelector('a').setAttribute('aria-current', 'page');
    }
    pageItem.querySelector('a').addEventListener('click', (event) => {
      event.preventDefault();
      loadPageFunction(page);
    });
    return pageItem;
  }

  // Add first page and ellipsis if necessary
  if (currentPage > 2) {
    paginationButtons.appendChild(createPageItem(1));
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
    paginationButtons.appendChild(createPageItem(i));
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
    paginationButtons.appendChild(createPageItem(numPages));
  }

  if (hasNext) {
    const nextPageItem = document.createElement('li');
    nextPageItem.className = 'usa-pagination__item usa-pagination__arrow';
    nextPageItem.innerHTML = `
      <a href="${headerAnchor}" class="usa-pagination__link usa-pagination__next-page" aria-label="Next page">
        <span class="usa-pagination__link-text">Next</span>
        <svg class="usa-icon" aria-hidden="true" role="img">
          <use xlink:href="/public/img/sprite.svg#navigate_next"></use>
        </svg>
      </a>
    `;
    nextPageItem.querySelector('a').addEventListener('click', (event) => {
      event.preventDefault();
      loadPageFunction(currentPage + 1);
    });
    paginationButtons.appendChild(nextPageItem);
  }
}

/**
 * A helper that toggles content/ no content/ no search results
 *
*/
const updateDisplay = (data, dataWrapper, noDataWrapper, noSearchResultsWrapper, searchTermHolder, currentSearchTerm) => {
  const { unfiltered_total, total } = data;

  const showElement = (element) => element.classList.remove('display-none');
  const hideElement = (element) => element.classList.add('display-none');
  if (searchTermHolder)
    searchTermHolder.innerHTML = '';

  if (unfiltered_total) {
    if (total) {
      showElement(dataWrapper);
      hideElement(noSearchResultsWrapper);
      hideElement(noDataWrapper);
    } else {
      if (searchTermHolder)
        searchTermHolder.innerHTML = currentSearchTerm;
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
const unsetHeader = (header) => {
  header.removeAttribute('aria-sort');
  let headerName = header.innerText;
  const headerLabel = `${headerName}', sortable column, currently unsorted"`;
  const headerButtonLabel = `Click to sort by ascending order.`;
  header.setAttribute("aria-label", headerLabel);
  header.querySelector('.usa-table__header__button').setAttribute("title", headerButtonLabel);
};

/**
 * An IIFE that listens for DOM Content to be loaded, then executes.  This function
 * initializes the domains list and associated functionality on the home page of the app.
 *
 */
document.addEventListener('DOMContentLoaded', function() {
  let domainsWrapper = document.querySelector('.domains__table-wrapper');

  if (domainsWrapper) {
    let currentSortBy = 'id';
    let currentOrder = 'asc';
    let noDomainsWrapper = document.querySelector('.domains__no-data');
    let noSearchResultsWrapper = document.querySelector('.domains__no-search-results');
    let hasLoaded = false;
    let currentSearchTerm = ''
    let domainsSearchInput = document.getElementById('domains__search-field');
    let domainsSearchSubmit = document.getElementById('domains__search-field-submit');
    let tableHeaders = document.querySelectorAll('.domains__table th[data-sortable]');
    let tableAnnouncementRegion = document.querySelector('.domains__table-wrapper  .usa-table__announcement-region');
    let searchTermHolder = document.querySelector('.domains__search-term');

    /**
     * Loads rows in the domains list, as well as updates pagination around the domains list
     * based on the supplied attributes.
     * @param {*} page - the page number of the results (starts with 1)
     * @param {*} sortBy - the sort column option
     * @param {*} order - the sort order {asc, desc}
     * @param {*} loaded - control for the scrollToElement functionality
     * @param {*} searchTerm - the search term
     */
    function loadDomains(page, sortBy = currentSortBy, order = currentOrder, loaded = hasLoaded, searchTerm = currentSearchTerm) {
      //fetch json of page of domains, given page # and sort
      fetch(`/get-domains-json/?page=${page}&sort_by=${sortBy}&order=${order}&search_term=${searchTerm}`)
        .then(response => response.json())
        .then(data => {
          if (data.error) {
            console.log('Error in AJAX call: ' + data.error);
            return;
          }

          // handle the display of proper messaging in the event that no domains exist in the list or search returns no results
          updateDisplay(data, domainsWrapper, noDomainsWrapper, noSearchResultsWrapper, searchTermHolder, currentSearchTerm);

          // identify the DOM element where the domain list will be inserted into the DOM
          const domainList = document.querySelector('.domains__table tbody');
          domainList.innerHTML = '';

          data.domains.forEach(domain => {
            const options = { year: 'numeric', month: 'short', day: 'numeric' };
            const expirationDate = domain.expiration_date ? new Date(domain.expiration_date) : null;
            const expirationDateFormatted = expirationDate ? expirationDate.toLocaleDateString('en-US', options) : '';
            const expirationDateSortValue = expirationDate ? expirationDate.getTime() : '';
            const actionUrl = domain.action_url;

            
            const row = document.createElement('tr');
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
                  aria-label="Status Information"
                  role="tooltip"
                >
                  <use aria-hidden="true" xlink:href="/public/img/sprite.svg#info_outline"></use>
                </svg>
              </td>
              <td>
                <a href="${actionUrl}">
                  <svg class="usa-icon" aria-hidden="true" focusable="false" role="img" width="24">
                    <use xlink:href="/public/img/sprite.svg#${domain.svg_icon}"></use>
                  </svg>
                  ${domain.action_label} <span class="usa-sr-only">${domain.name}</span>
                </a>
              </td>
            `;
            domainList.appendChild(row);
          });
          // initialize tool tips immediately after the associated DOM elements are added
          initializeTooltips();

          // Do not scroll on first page load
          if (loaded)
            ScrollToElement('id', 'domains-header');
          hasLoaded = true;

          // update pagination
          updatePagination(
            'domain',
            '#domains-pagination',
            '#domains-pagination .usa-pagination__counter',
            '#domains-header',
            loadDomains,
            data.page,
            data.num_pages,
            data.has_previous,
            data.has_next,
            data.total,
            currentSearchTerm
          );
          currentSortBy = sortBy;
          currentOrder = order;
          currentSearchTerm = searchTerm;
        })
        .catch(error => console.error('Error fetching domains:', error));
    }

    // Add event listeners to table headers for sorting
    tableHeaders.forEach(header => {
      header.addEventListener('click', function() {
        const sortBy = this.getAttribute('data-sortable');
        let order = 'asc';
        // sort order will be ascending, unless the currently sorted column is ascending, and the user
        // is selecting the same column to sort in descending order
        if (sortBy === currentSortBy) {
          order = currentOrder === 'asc' ? 'desc' : 'asc';
        }
        // load the results with the updated sort
        loadDomains(1, sortBy, order);
      });
    });

    domainsSearchSubmit.addEventListener('click', function(e) {
      e.preventDefault();
      currentSearchTerm = domainsSearchInput.value;
      loadDomains(1, 'id', 'asc');
      resetheaders();
    })

    // Reset UI and accessibility
    function resetheaders() {
      tableHeaders.forEach(header => {
        // unset sort UI in headers
        unsetHeader(header);
      });
      // Reset the announcement region
      tableAnnouncementRegion.innerHTML = '';
    }

    function resetSearch() {
      domainsSearchInput.value = '';
      loadDomains(1, 'id', 'asc', hasLoaded, '');
      resetheaders();
    }

    resetButton = document.querySelector('.domains__reset-button');
    if (resetButton) {
      resetButton.addEventListener('click', function() {
        resetSearch();
      });
    }

    // Load the first page initially
    loadDomains(1);
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
 * initializes the domain requests list and associated functionality on the home page of the app.
 *
 */
document.addEventListener('DOMContentLoaded', function() {
  let domainRequestsSectionWrapper = document.querySelector('.domain-requests');
  let domainRequestsWrapper = document.querySelector('.domain-requests__table-wrapper');

  if (domainRequestsWrapper) {
    let currentSortBy = 'id';
    let currentOrder = 'asc';
    let noDomainRequestsWrapper = document.querySelector('.domain-requests__no-data');
    let noSearchResultsWrapper = document.querySelector('.domain-requests__no-search-results');
    let hasLoaded = false;
    let currentSearchTerm = ''
    let domainRequestsSearchInput = document.getElementById('domain-requests__search-field');
    let domainRequestsSearchSubmit = document.getElementById('domain-requests__search-field-submit');
    let tableHeaders = document.querySelectorAll('.domain-requests__table th[data-sortable]');
    let tableAnnouncementRegion = document.querySelector('.domain-requests__table-wrapper .usa-table__announcement-region');
    let searchTermHolder = document.querySelector('.domain-requests__search-term');

    /**
     * Delete is actually a POST API that requires a csrf token. The token will be waiting for us in the template as a hidden input.
     * @param {*} domainRequestPk - the identifier for the request that we're deleting
     * @param {*} pageToDisplay - If we're deleting the last item on a page that is not page 1, we'll need to display the previous page
    */
    function deleteDomainRequest(domainRequestPk,pageToDisplay) {
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
        loadDomainRequests(pageToDisplay, currentSortBy, currentOrder, hasLoaded, currentSearchTerm);
      })
      .catch(error => console.error('Error fetching domain requests:', error));
    }
  
    // Helper function to get the CSRF token from the cookie
    function getCsrfToken() {
      return document.querySelector('input[name="csrfmiddlewaretoken"]').value;
    }

    /**
     * Loads rows in the domain requests list, as well as updates pagination around the domain requests list
     * based on the supplied attributes.
     * @param {*} page - the page number of the results (starts with 1)
     * @param {*} sortBy - the sort column option
     * @param {*} order - the sort order {asc, desc}
     * @param {*} loaded - control for the scrollToElement functionality
     * @param {*} searchTerm - the search term
     */
    function loadDomainRequests(page, sortBy = currentSortBy, order = currentOrder, loaded = hasLoaded, searchTerm = currentSearchTerm) {
      //fetch json of page of domain requests, given page # and sort
      fetch(`/get-domain-requests-json/?page=${page}&sort_by=${sortBy}&order=${order}&search_term=${searchTerm}`)
        .then(response => response.json())
        .then(data => {
          if (data.error) {
            console.log('Error in AJAX call: ' + data.error);
            return;
          }

          // handle the display of proper messaging in the event that no requests exist in the list or search returns no results
          updateDisplay(data, domainRequestsWrapper, noDomainRequestsWrapper, noSearchResultsWrapper, searchTermHolder, currentSearchTerm);

          // identify the DOM element where the domain request list will be inserted into the DOM
          const tbody = document.querySelector('.domain-requests__table tbody');
          tbody.innerHTML = '';

          // remove any existing modal elements from the DOM so they can be properly re-initialized
          // after the DOM content changes and there are new delete modal buttons added
          unloadModals();

          let needsDeleteColumn = false;

          data.domain_requests.forEach(request => {
            if (request.is_deletable)
              needsDeleteColumn = true;
          });

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
              delheader.setAttribute('class', 'delete-header');
              delheader.innerHTML = `
                <span class="usa-sr-only">Delete Action</span>`;
              let tableHeaderRow = document.querySelector('.domain-requests__table thead tr');
              tableHeaderRow.appendChild(delheader);
            }
          }

          data.domain_requests.forEach(request => {
            const options = { year: 'numeric', month: 'short', day: 'numeric' };
            const domainName = request.requested_domain ? request.requested_domain : `New domain request <br><span class="text-base font-body-xs">(${utcDateString(request.created_at)})</span>`;
            const actionUrl = request.action_url;
            const actionLabel = request.action_label;
            const submissionDate = request.submission_date ? new Date(request.submission_date).toLocaleDateString('en-US', options) : `<span class="text-base">Not submitted</span>`;
            
            // Even if the request is not deletable, we may need this empty string for the td if the deletable column is displayed
            let modalTrigger = '';

            // If the request is deletable, create modal body and insert it
            if (request.is_deletable) {
              let modalHeading = '';
              let modalDescription = '';

              if (request.requested_domain) {
                modalHeading = `Are you sure you want to delete ${request.requested_domain}?`;
                modalDescription = 'This will remove the domain request from the .gov registrar. This action cannot be undone.';
              } else {
                if (request.created_at) {
                  modalHeading = 'Are you sure you want to delete this domain request?';
                  modalDescription = `This will remove the domain request (created ${utcDateString(request.created_at)}) from the .gov registrar. This action cannot be undone`;
                } else {
                  modalHeading = 'Are you sure you want to delete New domain request?';
                  modalDescription = 'This will remove the domain request from the .gov registrar. This action cannot be undone.';
                }
              }

              modalTrigger = `
                <a 
                  role="button" 
                  id="button-toggle-delete-domain-alert-${request.id}"
                  href="#toggle-delete-domain-alert-${request.id}"
                  class="usa-button--unstyled text-no-underline late-loading-modal-trigger"
                  aria-controls="toggle-delete-domain-alert-${request.id}"
                  data-open-modal
                >
                  <svg class="usa-icon" aria-hidden="true" focusable="false" role="img" width="24">
                    <use xlink:href="/public/img/sprite.svg#delete"></use>
                  </svg> Delete <span class="usa-sr-only">${domainName}</span>
                </a>`

              const modalSubmit = `
                <button type="button"
                class="usa-button usa-button--secondary usa-modal__submit"
                data-pk = ${request.id}
                name="delete-domain-request">Yes, delete request</button>
              `

              const modal = document.createElement('div');
              modal.setAttribute('class', 'usa-modal');
              modal.setAttribute('id', `toggle-delete-domain-alert-${request.id}`);
              modal.setAttribute('aria-labelledby', 'Are you sure you want to continue?');
              modal.setAttribute('aria-describedby', 'Domain will be removed');
              modal.setAttribute('data-force-action', '');

              modal.innerHTML = `
                <div class="usa-modal__content">
                  <div class="usa-modal__main">
                    <h2 class="usa-modal__heading" id="modal-1-heading">
                      ${modalHeading}
                    </h2>
                    <div class="usa-prose">
                      <p id="modal-1-description">
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

              domainRequestsSectionWrapper.appendChild(modal);
            }

            const row = document.createElement('tr');
            row.innerHTML = `
              <th scope="row" role="rowheader" data-label="Domain name">
                ${domainName}
              </th>
              <td data-sort-value="${new Date(request.submission_date).getTime()}" data-label="Date submitted">
                ${submissionDate}
              </td>
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
              ${needsDeleteColumn ? '<td>'+modalTrigger+'</td>' : ''}
            `;
            tbody.appendChild(row);
          });

          // initialize modals immediately after the DOM content is updated
          initializeModals();

          // Now the DOM and modals are ready, add listeners to the submit buttons
          const modals = document.querySelectorAll('.usa-modal__content');

          modals.forEach(modal => {
            const submitButton = modal.querySelector('.usa-modal__submit');
            const closeButton = modal.querySelector('.usa-modal__close');
            submitButton.addEventListener('click', function() {
              pk = submitButton.getAttribute('data-pk');
              // Close the modal to remove the USWDS UI locl classes
              closeButton.click();
              // If we're deleteing the last item on a page that is not page 1, we'll need to refresh the display to the previous page
              let pageToDisplay = data.page;
              if (data.total == 1 && data.unfiltered_total > 1) {
                pageToDisplay--;
              }
              deleteDomainRequest(pk, pageToDisplay);
            });
          });

          // Do not scroll on first page load
          if (loaded)
            ScrollToElement('id', 'domain-requests-header');
          hasLoaded = true;

          // update the pagination after the domain requests list is updated
          updatePagination(
            'domain request',
            '#domain-requests-pagination',
            '#domain-requests-pagination .usa-pagination__counter',
            '#domain-requests-header',
            loadDomainRequests,
            data.page,
            data.num_pages,
            data.has_previous,
            data.has_next,
            data.total,
            currentSearchTerm
          );
          currentSortBy = sortBy;
          currentOrder = order;
          currentSearchTerm = searchTerm;
        })
        .catch(error => console.error('Error fetching domain requests:', error));
    }

    // Add event listeners to table headers for sorting
    tableHeaders.forEach(header => {
      header.addEventListener('click', function() {
        const sortBy = this.getAttribute('data-sortable');
        let order = 'asc';
        // sort order will be ascending, unless the currently sorted column is ascending, and the user
        // is selecting the same column to sort in descending order
        if (sortBy === currentSortBy) {
          order = currentOrder === 'asc' ? 'desc' : 'asc';
        }
        loadDomainRequests(1, sortBy, order);
      });
    });

    domainRequestsSearchSubmit.addEventListener('click', function(e) {
      e.preventDefault();
      currentSearchTerm = domainRequestsSearchInput.value;
      loadDomainRequests(1, 'id', 'asc');
      resetheaders();
    })

    // Reset UI and accessibility
    function resetheaders() {
      tableHeaders.forEach(header => {
        // unset sort UI in headers
        unsetHeader(header);
      });
      // Reset the announcement region
      tableAnnouncementRegion.innerHTML = '';
    }

    function resetSearch() {
      domainRequestsSearchInput.value = '';
      loadDomainRequests(1, 'id', 'asc', hasLoaded, '');
      resetheaders();
    }

    resetButton = document.querySelector('.domain-requests__reset-button');
    if (resetButton) {
      resetButton.addEventListener('click', function() {
        resetSearch();
      });
    }

    // Load the first page initially
    loadDomainRequests(1);
  }
});



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

  // Hookup all edit buttons to the `handleEditButtonClick` function
  setupListener();

  // Show the input fields if an error exists
  showInputOnErrorFields();
})();
