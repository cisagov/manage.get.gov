/** Strings announced to assistive technology users. */
var ARIA = {
  QUESTION_REMOVED: "Previous follow-up question removed",
  QUESTION_ADDED: "New follow-up question required"
}

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

/** Inputs which are required (if visible). */
var requiredInputs = {}

/** Helper function. Removes `required` attribute. */
function removeRequired(el) {
  const inputs = el.querySelectorAll("input");
  for (const input of inputs) {
    if (input.required) {
      requiredInputs[input.id] = true;
      input.removeAttribute("required");
    }
  }
}

/** Helper function. Adds `required` attribute. */
function markRequired(el) {
  const inputs = el.querySelectorAll("input");
  for (const input of inputs) {
    if (input.id in requiredInputs) {
      input.setAttribute("required", "");
    }
  }
}

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
function setSelected(radioButton) {
  selected[radioButton.name] = radioButton;
}

/** Helper function. Announces changes to assistive technology users. */
function announce(id, text) {
  const liveRegion = document.getElementById(id + "-live-region");
  liveRegion.innerHTML = text;
}

/** On radio button selection change, handles associated toggleables. */
function handleToggle(e) {
  // remove toggleable for deselected radio button
  const selectionExists = e.target.name in selected;

  if (selectionExists) {
    const hasToggleable = selected[e.target.name].id in radioToggles;
    if (hasToggleable) {
      const prevRadio = selected[e.target.name];
      const prevToggleable = radioToggles[prevRadio.id];
  
      const selectionHasChanged = (e.target != prevRadio);
      const prevSelectionVisible = (prevToggleable.style.visibility === "visible");
      if (selectionHasChanged && prevSelectionVisible) {
        makeHidden(prevToggleable);
        removeRequired(prevToggleable);
        announce(prevToggleable.id, ARIA.QUESTION_REMOVED);
      }
    }
  }

  // if the currently selected radio button has a toggle
  // make it visible
  if (e.target.id in radioToggles) {
    const toggleable = radioToggles[e.target.id];
    setSelected(e.target);
    markRequired(toggleable);
    makeVisible(toggleable);
    announce(toggleable.id, ARIA.QUESTION_ADDED);
  }
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
    removeRequired(hidden);
  }
})();

/**
 * An IIFE that adds onChange listeners to radio buttons.
 * 
 * An element with `toggle-by="<id>"` will be hidden/shown
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
    console.log('toggleable :', toggleable);
    console.log('toggleable.id :', toggleable.id);

    for (const id of radioIDs) {
      radioToggles[id] = toggleable;
      // if it is already selected, track that
      if (document.getElementById(id).selected) setSelected(radioButton);
    }
  }

  // all radio buttons must react to selection changes
  const radioButtons = document.querySelectorAll('input[type="radio"]');
  for (const radioButton of Array.from(radioButtons)) {
    radioButton.addEventListener('change', handleToggle);
  }
})();
