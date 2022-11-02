/** Strings announced to assistive technology users. */
var ARIA = {
  QUESTION_REMOVED: "Previous follow-up question removed",
  QUESTION_ADDED: "New follow-up question required"
}

var REQUIRED = "required";
var INPUT = "input";

/** Helper function. Makes an element invisible. */
function makeHidden(el) {
  el.style.position = "absolute";
  el.style.left = "-100vw";
  // The choice of `visiblity: hidden`
  // over `display: none` is due to
  // UX: the former will allow CSS
  // transitions when the elements appear.
  el.style.visibility = "hidden";
}

/** Helper function. Makes visible a perviously hidden element. */
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

/** Helper function. Removes `required` attribute from input. */
const removeRequired = input => input.removeAttribute(REQUIRED);

/** Helper function. Adds `required` attribute to input. */
const setRequired = input => input.setAttribute(REQUIRED, "");

/** Helper function. Removes `checked` attribute from input. */
const removeChecked = input => input.checked = false;

/** Helper function. Adds `checked` attribute to input. */
const setChecked = input => input.checked = true;

/** Helper function. Creates and returns a live region element. */
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
 * Helper function. Tracks state of selected radio button.
 * 
 * This is required due to JavaScript not having a native
 * event trigger for "deselect" on radio buttons. Tracking
 * which button has been deselected (and hiding the associated
 * toggleable) is a manual task.
 * */
function rememberSelected(radioButton) {
  selected[radioButton.name] = radioButton;
}

/** Helper function. Announces changes to assistive technology users. */
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

/** On radio button selection change, handles associated toggleables. */
function handleToggle(e) {
  // hide any previously visible HTML associated with previously selected radio buttons
  hideToggleable(e);
  // display any HTML associated with the newly selected radio button
  revealToggleable(e);
}

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
