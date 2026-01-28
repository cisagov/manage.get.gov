var DEFAULT_ERROR = "Please check this field for errors.";
var ERROR = "error";
var SUCCESS = "success";

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

/** Asyncronously fetches JSON. No error handling. */
function fetchJSON(endpoint, callback, url="/api/v1/") {
    const xhr = new XMLHttpRequest();
    xhr.open('GET', url + endpoint);
    xhr.send();
    xhr.onload = function() {
      if (xhr.status != 200) return;
      callback(JSON.parse(xhr.response));
    };
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
        toggleInputValidity(el, (response && response.available), response.message);
        announce(el.id, response.message);
    
        // Determines if we ignore the field if it is just blank
        let ignore_blank = el.classList.contains("blank-ok")
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
let inputs = Array.from(document.querySelectorAll('.repeatable-form input'));

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

/**
 * Removes form errors surrounding a form input
 */
function removeFormErrors(input, removeStaleAlerts=false){
    // Remove error message
    let errorMessage = document.getElementById(`${input.id}__error-message`);
    if (errorMessage) {
        errorMessage.remove();
    } else{
        return;
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
        let staleAlerts = document.querySelectorAll(".usa-alert--error");
        for (let alert of staleAlerts) {
            // Don't remove the error associated with the input
            if (alert.id !== `${input.id}--toast`) {
                alert.remove();
            }
        }
    }
}

export function initDomainValidators() {
    "use strict";
    const needsValidation = document.querySelectorAll('[validate]');
    for (const input of needsValidation) {
        input.addEventListener('input', handleInputValidation);
    }
    
    // Listening for ALL clicks on buttons with validate-for
    document.addEventListener('click', function(e) {
        const button = e.target.closest('button[validate-for]');
        if (!button) return;  // If not a validate button, ignore
        
        const targetInputId = button.getAttribute('validate-for');

        // Alternative domain buttons always point at formset inputs
        if (targetInputId && targetInputId.includes('alternative_domain')) {
            validateFormsetInputs(e, button);
        } else {
            validateFieldInput(e);
        }
    });
}