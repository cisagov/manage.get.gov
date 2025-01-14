import { hideElement, showElement } from './helpers.js';

export function loadInitialValuesForComboBoxes() {
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
}
