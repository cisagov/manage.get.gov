import { showElement, hideElement, scrollToElement } from './helpers';
import { removeErrorsFromElement, removeFormErrors } from './form-helpers';

export class DSDataForm {
    constructor() {
        this.addDSDataButton = document.getElementById('dsdata-add-button');
        this.addDSDataForm = document.querySelector('.add-dsdata-form');
        this.formChanged = false;
        this.callback = null;

        // Bind event handlers to maintain 'this' context
        this.handleAddFormClick = this.handleAddFormClick.bind(this);
        this.handleEditClick = this.handleEditClick.bind(this);
        this.handleDeleteClick = this.handleDeleteClick.bind(this);
        this.handleDeleteKebabClick = this.handleDeleteKebabClick.bind(this);
        this.handleCancelClick = this.handleCancelClick.bind(this);
        this.handleCancelAddFormClick = this.handleCancelAddFormClick.bind(this);
    }

    /**
     * Initialize the DSDataForm by setting up display and event listeners.
     */
    init() {
        this.initializeDSDataFormDisplay();
        this.initializeEventListeners();
    }


    /**
     * Determines the initial display state of the DS data form,
     * handling validation errors and setting visibility of elements accordingly.
     */
    initializeDSDataFormDisplay() {

        // This check indicates that there is an Add DS Data form
        // and that form has errors in it. In this case, show the form, and indicate that the form has
        // changed.
        if (this.addDSDataForm && this.addDSDataForm.querySelector('.usa-input--error')) {
            showElement(this.addDSDataForm);
            this.formChanged = true;
        }

        // handle display of table view errors
        // if error exists in an edit-row, make that row show, and readonly row hide
        const formTable = document.getElementById('dsdata-table')
        if (formTable) {
            const editRows = formTable.querySelectorAll('.edit-row');
            editRows.forEach(editRow => {
                if (editRow.querySelector('.usa-input--error')) {
                    const readOnlyRow = editRow.previousElementSibling;
                    this.formChanged = true;
                    showElement(editRow);
                    hideElement(readOnlyRow);
                }
            })
        }

    }

    /**
     * Attaches event listeners to relevant UI elements for interaction handling.
     */
    initializeEventListeners() {
        this.addDSDataButton.addEventListener('click', this.handleAddFormClick);
    
        const editButtons = document.querySelectorAll('.dsdata-edit');
        editButtons.forEach(editButton => {
            editButton.addEventListener('click', this.handleEditClick);
        });
    
        const cancelButtons = document.querySelectorAll('.dsdata-cancel');
        cancelButtons.forEach(cancelButton => {
            cancelButton.addEventListener('click', this.handleCancelClick);
        });

        const cancelAddFormButtons = document.querySelectorAll('.dsdata-cancel-add-form');
        cancelAddFormButtons.forEach(cancelAddFormButton => {
            cancelAddFormButton.addEventListener('click', this.handleCancelAddFormClick);
        });

        const deleteButtons = document.querySelectorAll('.dsdata-delete');
        deleteButtons.forEach(deleteButton => {
            deleteButton.addEventListener('click', this.handleDeleteClick);
        });

        const deleteKebabButtons = document.querySelectorAll('.dsdata-delete-kebab');
        deleteKebabButtons.forEach(deleteKebabButton => {
            deleteKebabButton.addEventListener('click', this.handleDeleteKebabClick);
        });

        const inputs = document.querySelectorAll("input[type='text'], textarea");
        inputs.forEach(input => {
            input.addEventListener("input", () => {
                this.formChanged = true;
            });
        });

        const selects = document.querySelectorAll("select");
        selects.forEach(select => {
            select.addEventListener("change", () => {
                this.formChanged = true;
            });
        });

        // Set event listeners on the submit buttons for the modals. Event listeners
        // should execute the callback function, which has its logic updated prior
        // to modal display
        const unsaved_changes_modal = document.getElementById('unsaved-changes-modal');
        if (unsaved_changes_modal) {
            const submitButton = document.getElementById('unsaved-changes-click-button');
            const closeButton = unsaved_changes_modal.querySelector('.usa-modal__close');
            submitButton.addEventListener('click', () => {
                closeButton.click();
                this.executeCallback();
            });
        }
        const cancel_changes_modal = document.getElementById('cancel-changes-modal');
        if (cancel_changes_modal) {
            const submitButton = document.getElementById('cancel-changes-click-button');
            const closeButton = cancel_changes_modal.querySelector('.usa-modal__close');
            submitButton.addEventListener('click', () => {
                closeButton.click();
                this.executeCallback();
            });
        }
        const delete_modal = document.getElementById('delete-modal');
        if (delete_modal) {
            const submitButton = document.getElementById('delete-click-button');
            const closeButton = delete_modal.querySelector('.usa-modal__close');
            submitButton.addEventListener('click', () => {
                closeButton.click();
                this.executeCallback();
            });
        }
        const disable_dnssec_modal = document.getElementById('disable-dnssec-modal');
        if (disable_dnssec_modal) {
            const submitButton = document.getElementById('disable-dnssec-click-button');
            const closeButton = disable_dnssec_modal.querySelector('.usa-modal__close');
            submitButton.addEventListener('click', () => {
                closeButton.click();
                this.executeCallback();
            });
        }

    }

    /**
     * Executes a stored callback function if defined, otherwise logs a warning.
     */
    executeCallback() {
        if (this.callback) {
            this.callback();
            this.callback = null;
        } else {
            console.warn("No callback function set.");
        }
    }

    /**
     * Handles clicking the 'Add DS data' button, showing the form if needed.
     * @param {Event} event - Click event
     */
    handleAddFormClick(event) {
        this.callback = () => {
            // Check if any other edit row is currently visible and hide it
            document.querySelectorAll('tr.edit-row:not(.display-none)').forEach(openEditRow => {
                this.resetEditRowAndFormAndCollapseEditRow(openEditRow);
            });
            if (this.addDSDataForm) {
                // Check if this.addDSDataForm is visible (i.e., does not have 'display-none')
                if (!this.addDSDataForm.classList.contains('display-none')) {
                    this.resetAddDSDataForm();
                }
                // show add ds data form
                showElement(this.addDSDataForm);
                // focus on key tag in the form
                let keyTagInput = this.addDSDataForm.querySelector('input[name$="-key_tag"]');
                if (keyTagInput) {
                    keyTagInput.focus();
                }
            } else {
                this.addAlert("error", "You’ve reached the maximum amount of DS Data records (8). To add another record, you’ll need to delete one of your saved records.");
            }
        };
        if (this.formChanged) {
            //------- Show the unsaved changes confirmation modal
            let modalTrigger = document.querySelector("#unsaved_changes_trigger");
            if (modalTrigger) {
                modalTrigger.click();
            }
        } else {
            this.executeCallback();
        }
    }

    /**
     * Handles clicking an 'Edit' button on a readonly row, which hides the readonly row
     * and displays the edit row, after performing some checks and possibly displaying modal.
     * @param {Event} event - Click event
     */
    handleEditClick(event) {
        let editButton = event.target;
        let readOnlyRow = editButton.closest('tr'); // Find the closest row
        let editRow = readOnlyRow.nextElementSibling; // Get the next row
        if (!editRow || !readOnlyRow) {
            console.warn("Expected DOM element but did not find it");
            return;
        }
        this.callback = () => {
            // Check if any other edit row is currently visible and hide it
            document.querySelectorAll('tr.edit-row:not(.display-none)').forEach(openEditRow => {
                this.resetEditRowAndFormAndCollapseEditRow(openEditRow);
            });
            // Check if this.addDSDataForm is visible (i.e., does not have 'display-none')
            if (this.addDSDataForm && !this.addDSDataForm.classList.contains('display-none')) {
                this.resetAddDSDataForm();
            }
            // hide and show rows as appropriate
            hideElement(readOnlyRow);
            showElement(editRow);
        };
        if (this.formChanged) {
            //------- Show the unsaved changes confirmation modal
            let modalTrigger = document.querySelector("#unsaved_changes_trigger");
            if (modalTrigger) {
                modalTrigger.click();
            }
        } else {
            this.executeCallback();
        }
    }

    /**
     * Handles clicking a 'Delete' button on an edit row, which hattempts to delete the DS record
     * after displaying modal.
     * @param {Event} event - Click event
     */
    handleDeleteClick(event) {
        let deleteButton = event.target;
        let editRow = deleteButton.closest('tr');
        if (!editRow) {
            console.warn("Expected DOM element but did not find it");
            return;
        }
        this.deleteRow(editRow);
    }

    /**
     * Handles clicking a 'Delete' button on a readonly row in a kebab, which attempts to delete the DS record
     * after displaying modal.
     * @param {Event} event - Click event
     */
    handleDeleteKebabClick(event) {
        let deleteKebabButton = event.target;
        let accordionDiv = deleteKebabButton.closest('div'); 
        // hide the accordion
        accordionDiv.hidden = true;
        let readOnlyRow = deleteKebabButton.closest('tr'); // Find the closest row
        let editRow = readOnlyRow.nextElementSibling; // Get the next row
        if (!editRow) {
            console.warn("Expected DOM element but did not find it");
            return;
        }
        this.deleteRow(editRow);
    }

    /**
     * Deletes a DS record row. If there is only one DS record, prompt the user
     * that they will be disabling DNSSEC. Otherwise, prompt with delete confiration.
     * If deletion proceeds, the input fields are cleared, and the form is submitted.
     * @param {HTMLElement} editRow - The row corresponding to the DS record being deleted.
     */
    deleteRow(editRow) {
        // update the callback method
        this.callback = () => {
            hideElement(editRow);
            let deleteInput = editRow.querySelector("input[name$='-DELETE']");
            if (deleteInput) {
                deleteInput.checked = true;
            }
            const form = editRow.closest("form");
            if (form) form.submit();
        };
        // Check if at least 2 DS data records exist before the delete row action is taken
        const thirdDSData = document.getElementById('id_form-2-key_tag')
        if (thirdDSData) {
            let modalTrigger = document.querySelector('#delete_trigger');
            if (modalTrigger) {
                modalTrigger.click();
            }
        } else {
            let modalTrigger = document.querySelector('#disable_dnssec_trigger');
            if (modalTrigger) {
                modalTrigger.click();
            }
        }
    }

    /**
     * Handles the click event on the "Cancel" button in the add DS data form.
     * Resets the form fields and hides the add form section.
     * @param {Event} event - Click event
     */
    handleCancelAddFormClick(event) {
        this.callback = () => {
            this.resetAddDSDataForm();
        }
        if (this.formChanged) {
            // Show the cancel changes confirmation modal
            let modalTrigger = document.querySelector("#cancel_changes_trigger");
            if (modalTrigger) {
                modalTrigger.click();
            }
        } else {
            this.executeCallback();
        }
    }

    /**
     * Handles the click event for the cancel button within the table form.
     * 
     * This method identifies the edit row containing the cancel button and resets
     * it to its initial state, restoring the corresponding read-only row.
     * 
     * @param {Event} event - the click event triggered by the cancel button
     */
    handleCancelClick(event) {
        // get the cancel button that was clicked
        let cancelButton = event.target;
        // find the closest table row that contains the cancel button
        let editRow = cancelButton.closest('tr');
        this.callback = () => {
            if (editRow) {
                this.resetEditRowAndFormAndCollapseEditRow(editRow);
            } else {
                console.warn("Expected DOM element but did not find it");
            }
        }
        if (this.formChanged) {
            // Show the cancel changes confirmation modal
            let modalTrigger = document.querySelector("#cancel_changes_trigger");
            if (modalTrigger) {
                modalTrigger.click();
            }
        } else {
            this.executeCallback();
        }
    }

    /**
     * Resets the edit row, restores its original values, removes validation errors, 
     * and collapses the edit row while making the readonly row visible again.
     * @param {HTMLElement} editRow - The row that is being reset and collapsed.
     */
    resetEditRowAndFormAndCollapseEditRow(editRow) {
        let readOnlyRow = editRow.previousElementSibling; // Get the next row
        if (!editRow || !readOnlyRow) {
            console.warn("Expected DOM element but did not find it");
            return;
        }
        // reset the values set in editRow
        this.resetInputValuesInElement(editRow);
        // copy values from editRow to readOnlyRow
        this.copyEditRowToReadonlyRow(editRow, readOnlyRow);
        // remove errors from the editRow
        removeErrorsFromElement(editRow);
        // remove errors from the entire form
        removeFormErrors();
        // reset formChanged
        this.resetFormChanged();
        // hide and show rows as appropriate
        hideElement(editRow);
        showElement(readOnlyRow);
    }

    /**
     * Resets the 'Add DS data' form by clearing its input fields, removing errors, 
     * and hiding the form to return it to its initial state.
     */
    resetAddDSDataForm() {
        if (this.addDSDataForm) {
            // reset the values set in addDSDataForm
            this.resetInputValuesInElement(this.addDSDataForm);
            // remove errors from the addDSDataForm
            removeErrorsFromElement(this.addDSDataForm);
            // remove errors from the entire form
            removeFormErrors();
            // reset formChanged
            this.resetFormChanged();
            // hide the addDSDataForm
            hideElement(this.addDSDataForm);
        }
    }

    /**
     * Resets all text input fields within the specified DOM element to their initial values.
     * Triggers an 'input' event to ensure any event listeners update accordingly.
     * @param {HTMLElement} domElement - The parent element containing text input fields to be reset.
     */
    resetInputValuesInElement(domElement) {
        const inputEvent = new Event('input');
        const changeEvent = new Event('change');
        // Reset text inputs
        const inputs = document.querySelectorAll("input[type='text'], textarea");
        inputs.forEach(input => {
            // Reset input value to its initial stored value
            input.value = input.dataset.initialValue;
            // Dispatch input event to update any event-driven changes
            input.dispatchEvent(inputEvent);
        });
        // Reset select elements
        let selects = domElement.querySelectorAll("select");
        selects.forEach(select => {
            // Reset select value to its initial stored value
            select.value = select.dataset.initialValue;
            // Dispatch change event to update any event-driven changes
            select.dispatchEvent(changeEvent);
        });
    }

    /**
     * Copies values from the editable row's text inputs into the corresponding
     * readonly row cells, formatting them appropriately.
     * @param {HTMLElement} editRow - The row containing editable input fields.
     * @param {HTMLElement} readOnlyRow - The row where values will be displayed in a non-editable format.
     */
    copyEditRowToReadonlyRow(editRow, readOnlyRow) {
        let keyTagInput = editRow.querySelector("input[type='text']");
        let selects = editRow.querySelectorAll("select");
        let digestInput = editRow.querySelector("textarea");
        let tds = readOnlyRow.querySelectorAll("td");

        // Copy the key tag input value
        if (keyTagInput) {
            tds[0].innerText = keyTagInput.value || "";
        }

        // Copy select values (showing the selected label instead of value)
        if (selects[0]) {
            let selectedOption = selects[0].options[selects[0].selectedIndex];
            if (tds[1]) {
                tds[1].innerHTML = `<span class="ellipsis ellipsis--15">${selectedOption ? selectedOption.text : ""}</span>`;
            }
        }
        if (selects[1]) {
            let selectedOption = selects[1].options[selects[1].selectedIndex];
            if (tds[2]) {
                tds[2].innerText = selectedOption ? selectedOption.text : "";
            }
        }

        // Copy the digest input value
        if (digestInput) {
            tds[3].innerHTML = `<span class="ellipsis ellipsis--23">${digestInput.value || ""}</span>`;
        }
    }

    /**
     * Resets the form change state.
     * This method marks the form as unchanged by setting `formChanged` to false.
     * It is useful for tracking whether a user has modified any form fields.
     */
    resetFormChanged() {
        this.formChanged = false;
    }

    /**
     * Removes all existing alert messages from the main content area.
     * This ensures that only the latest alert is displayed to the user.
     */
    resetAlerts() {
        const mainContent = document.getElementById("main-content");
        if (mainContent) {
            // Remove all alert elements within the main content area
            mainContent.querySelectorAll(".usa-alert:not(.usa-alert--do-not-reset)").forEach(alert => alert.remove());
        } else {
            console.warn("Expecting main-content DOM element");
        }
    }

    /**
     * Displays an alert message at the top of the main content area.
     * It first removes any existing alerts before adding a new one to ensure only the latest alert is visible.
     * @param {string} level - The alert level (e.g., 'error', 'success', 'warning', 'info').
     * @param {string} message - The message to display inside the alert.
     */
    addAlert(level, message) {
        this.resetAlerts(); // Remove any existing alerts before adding a new one
        
        const mainContent = document.getElementById("main-content");
        if (!mainContent) return;

        // Create a new alert div with appropriate classes based on alert level
        const alertDiv = document.createElement("div");
        alertDiv.className = `usa-alert usa-alert--${level} usa-alert--slim margin-bottom-2`;
        alertDiv.setAttribute("role", "alert"); // Add the role attribute

        // Create the alert body to hold the message text
        const alertBody = document.createElement("div");
        alertBody.className = "usa-alert__body";
        alertBody.textContent = message;

        // Append the alert body to the alert div and insert it at the top of the main content area
        alertDiv.appendChild(alertBody);
        mainContent.insertBefore(alertDiv, mainContent.firstChild);

        // Scroll the page to make the alert visible to the user
        scrollToElement("class", "usa-alert__body");
    }
}

/**
 * Initializes the DSDataForm when the DOM is fully loaded.
 */
export function initFormDSData() {
    document.addEventListener('DOMContentLoaded', () => {
        if (document.getElementById('dsdata-add-button')) {
            const dsDataForm = new DSDataForm();
            dsDataForm.init();
        }
    });
}
