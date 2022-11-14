/**
 * @file get-gov.js includes custom code for the .gov registrar.
 *
 * Constants and helper functions are at the top.
 * Event handlers are in the middle.
 * Initialization (run-on-load) stuff goes at the bottom.
 */

/** Strings announced to assistive technology users. */
var ARIA = {
  QUESTION_REMOVED: "Previous follow-up question removed",
  QUESTION_ADDED: "New follow-up question required"
}

var DEFAULT_ERROR = "Please check this field for errors.";

var REQUIRED = "required";
var INPUT = "input";

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

/** Executes `func` once per selected child of a given element. */
function forEachChild(el, selector, func) {
  const children = el.querySelectorAll(selector);
  for (const child of children) {
    func(child)
  }
}

/** Removes `required` attribute from input. */
const removeRequired = input => input.removeAttribute(REQUIRED);

/** Adds `required` attribute to input. */
const setRequired = input => input.setAttribute(REQUIRED, "");

/** Removes `checked` attribute from input. */
const removeChecked = input => input.checked = false;

/** Adds `checked` attribute to input. */
const setChecked = input => input.checked = true;

/** Creates and returns a live region element. */
function createLiveRegion(id) {
  const liveRegion = document.createElement("div");
  liveRegion.setAttribute("role", "region");
  liveRegion.setAttribute("aria-live", "polite");
  liveRegion.setAttribute("id", id + "-live-region");
  liveRegion.classList.add("sr-only");
  document.body.appendChild(liveRegion);
  return liveRegion;
}

/** Currently selected radio buttons. */
var selected = {};

/** Mapping of radio buttons to the toggleables they control. */
var radioToggles = {};


/**
 * Tracks state of selected radio button.
 *
 * This is required due to JavaScript not having a native
 * event trigger for "deselect" on radio buttons. Tracking
 * which button has been deselected (and hiding the associated
 * toggleable) is a manual task.
 * */
function rememberSelected(radioButton) {
  selected[radioButton.name] = radioButton;
}

/** Announces changes to assistive technology users. */
function announce(id, text) {
  const liveRegion = document.getElementById(id + "-live-region");
  liveRegion.innerHTML = text;
}

/** 
 * Used by an event handler to hide HTML.
 *
 * Hides any previously visible HTML associated with
 * previously selected radio buttons.
 */
function hideToggleable(e) {
  // has any button in this radio button group been selected?
  const selectionExists = e.target.name in selected;
  if (selectionExists) {
    // does the selection have any hidden content associated with it?
    const hasToggleable = selected[e.target.name].id in radioToggles;
    if (hasToggleable) {
      const prevRadio = selected[e.target.name];
      const prevToggleable = radioToggles[prevRadio.id];

      // is this event handler for a different button?
      const selectionHasChanged = (e.target != prevRadio);
      // is the previous button's content still visible?
      const prevSelectionVisible = (prevToggleable.style.visibility !== "hidden");
      if (selectionHasChanged && prevSelectionVisible) {
        makeHidden(prevToggleable);
        forEachChild(prevToggleable, INPUT, removeChecked);
        forEachChild(prevToggleable, INPUT, removeRequired);
        announce(prevToggleable.id, ARIA.QUESTION_REMOVED);
      }
    }
  }
}

function revealToggleable(e) {
  // if the currently selected radio button has a toggle
  // make it visible
  if (e.target.id in radioToggles) {
    const toggleable = radioToggles[e.target.id];
    rememberSelected(e.target);
    if (e.target.required) forEachChild(toggleable, INPUT, setRequired);
    makeVisible(toggleable);
    announce(toggleable.id, ARIA.QUESTION_ADDED);
  }
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
    // this is here for testing: in actual use, we might not want to
    // visually display these errors until the user tries to submit
    el.classList.add('usa-input--error');
  }
}

function _checkDomainAvailability(e) {
  const callback = (response) => {
    toggleInputValidity(e.target, (response && response.available));
    if (e.target.validity.valid) {
      e.target.classList.add('usa-input--success');
      // do other stuff, like display a toast?
    }
  }
  fetchJSON(`available/${e.target.value}`, callback);
}

/** Call the API to see if the domain is good. */
const checkDomainAvailability = debounce(_checkDomainAvailability);

// <<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>>
// Event handlers.

/** On radio button selection change, handles associated toggleables. */
function handleToggle(e) {
  // hide any previously visible HTML associated with previously selected radio buttons
  hideToggleable(e);
  // display any HTML associated with the newly selected radio button
  revealToggleable(e);
}

/** On input change, handles running any associated validators. */
function handleInputValidation(e) {
  const attribute = e.target.getAttribute("validate") || "";
  if (!attribute.length) return;
  const validators = attribute.split(" ");
  let isInvalid = false;
  for (const validator of validators) {
    switch (validator) {
      case "domain":
        checkDomainAvailability(e);
        break;
    }
  }
  toggleInputValidity(e.target, !isInvalid);
}

// <<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>>
// Initialization code.

/**
 * An IIFE that will attach validators to inputs.
 *
 * It looks for elements with `validate="<type> <type>"` and adds
 * change handlers for each known type.
 */
 (function validatorsInit() {
  "use strict";
  const needsValidation = document.querySelectorAll('[validate]');
  for(const input of needsValidation) {
    input.addEventListener('input', handleInputValidation);
  }
})();

/**
 * An IIFE that will hide any elements with `hide-on-load` attribute.
 *
 * Why not start with `hidden`? Because this is for use with form questions:
 * if Javascript fails, users will still need access to those questions.
 */
 (function hiddenInit() {
  "use strict";
  const hiddens = document.querySelectorAll('[hide-on-load]');
  for(const hidden of hiddens) {
    makeHidden(hidden);
    forEachChild(hidden, INPUT, removeRequired);
  }
})();

/**
 * An IIFE that adds onChange listeners to radio buttons.
 * 
 * An element with `toggle-by="<id>,<id>"` will be hidden/shown
 * by a radio button with `id="<id>"`.
 * 
 * It also inserts the ARIA live region to be used when
 * announcing show/hide to screen reader users.
 */
(function toggleInit() {
  "use strict";

  // get elements to show/hide
  const toggleables = document.querySelectorAll('[toggle-by]');

  for(const toggleable of toggleables) {
    // get the (comma-seperated) list of radio button ids
    // which trigger this toggleable to become visible
    const attribute = toggleable.getAttribute("toggle-by") || "";
    if (!attribute.length) continue;
    const radioIDs = attribute.split(",");

    createLiveRegion(toggleable.id)

    for (const id of radioIDs) {
      radioToggles[id] = toggleable;
      // if it is already selected, track that
      const radioButton = document.getElementById(id);
      if (radioButton.checked) rememberSelected(radioButton);
    }
  }

  // all radio buttons must react to selection changes
  const radioButtons = document.querySelectorAll('input[type="radio"]');
  for (const radioButton of Array.from(radioButtons)) {
    radioButton.addEventListener('change', handleToggle);
  }
})();
