import { hideElement, showElement, scrollToElement, toggleCaret } from './helpers.js';
import { initializeTooltips, initializeModals, unloadModals } from './helpers-uswds.js';

/**
 * An IIFE that changes the default clear behavior on comboboxes to the input field.
 * We want the search bar to act soley as a search bar.
 */
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
  }


