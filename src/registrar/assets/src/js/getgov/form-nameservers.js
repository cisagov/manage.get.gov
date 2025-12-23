import { showElement, hideElement, scrollToElement } from './helpers';
import { removeErrorsFromElement, removeFormErrors } from './form-helpers';

export class NameserverForm {
    constructor() {
        this.addNameserverButton = document.getElementById('nameserver-add-button');
        this.addNameserversForm = document.querySelector('.add-nameservers-form');
        this.domain = '';
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
     * Initialize the NameserverForm by setting up display and event listeners.
     */
    init() {
        this.initializeNameserverFormDisplay();
        this.initializeEventListeners();
    }


    /**
     * Determines the initial display state of the nameserver form,
     * handling validation errors and setting visibility of elements accordingly.
     */
    initializeNameserverFormDisplay() {

        const domainName = document.getElementById('id_form-0-domain');
        if (domainName) {
            this.domain = domainName.value;
        } else {
            console.warn("Form expects a dom element, id_form-0-domain");
        }

        // Check if exactly two nameserver forms exist: id_form-1-server is present but id_form-2-server is not
        const secondNameserver = document.getElementById('id_form-1-server');
        const thirdNameserver = document.getElementById('id_form-2-server'); // This should not exist

        // Check if there are error messages in the form (indicated by elements with class 'usa-alert--error')
        const errorMessages = document.querySelectorAll('.usa-alert--error');

        // This check indicates that there are exactly two forms (which is the case for the Add New Nameservers form)
        // and there is at least one error in the form. In this case, show the Add New Nameservers form, and 
        // indicate that the form has changed
        if (this.addNameserversForm && secondNameserver && !thirdNameserver && errorMessages.length > 0) {
            showElement(this.addNameserversForm);
            this.formChanged = true;
        }

        // This check indicates that there is either an Add New Nameservers form or an Add New Nameserver form
        // and that form has errors in it. In this case, show the form, and indicate that the form has
        // changed.
        if (this.addNameserversForm && this.addNameserversForm.querySelector('.usa-input--error')) {
            showElement(this.addNameserversForm);
            this.formChanged = true;
        }

        // handle display of table view errors
        // if error exists in an edit-row, make that row show, and readonly row hide
        const formTable = document.getElementById('nameserver-table')
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

        // hide ip in forms unless nameserver ends with domain name
        let formIndex = 0;
        while (document.getElementById('id_form-' + formIndex + '-domain')) {
            let serverInput = document.getElementById('id_form-' + formIndex + '-server');
            let ipInput = document.getElementById('id_form-' + formIndex + '-ip');
            if (serverInput && ipInput) {
                let serverValue = serverInput.value.trim(); // Get the value and trim spaces
                let ipParent = ipInput.parentElement; // Get the parent element of ipInput
        
                if (ipParent && !serverValue.endsWith('.' + this.domain)) { 
                    hideElement(ipParent); // Hide the parent element of ipInput
                }
            }
            formIndex++;
        }
    }

    /**
     * Attaches event listeners to relevant UI elements for interaction handling.
     */
    initializeEventListeners() {
        this.addNameserverButton.addEventListener('click', this.handleAddFormClick);
    
        const editButtons = document.querySelectorAll('.nameserver-edit');
        editButtons.forEach(editButton => {
            editButton.addEventListener('click', this.handleEditClick);
        });
    
        const cancelButtons = document.querySelectorAll('.nameserver-cancel');
        cancelButtons.forEach(cancelButton => {
            cancelButton.addEventListener('click', this.handleCancelClick);
        });

        const cancelAddFormButtons = document.querySelectorAll('.nameserver-cancel-add-form');
        cancelAddFormButtons.forEach(cancelAddFormButton => {
            cancelAddFormButton.addEventListener('click', this.handleCancelAddFormClick);
        });

        const deleteButtons = document.querySelectorAll('.nameserver-delete');
        deleteButtons.forEach(deleteButton => {
            deleteButton.addEventListener('click', this.handleDeleteClick);
        });

        const deleteKebabButtons = document.querySelectorAll('.nameserver-delete-kebab');
        deleteKebabButtons.forEach(deleteKebabButton => {
            deleteKebabButton.addEventListener('click', this.handleDeleteKebabClick);
        });

        const textInputs = document.querySelectorAll("input[type='text']");
        textInputs.forEach(input => {
            input.addEventListener("input", () => {
                this.formChanged = true;
            });
        });

        // Add a specific listener for 'id_form-{number}-server' inputs to make
        // nameserver forms 'smart'. Inputs on server field will change the
        // display value of the associated IP address field.
        let formIndex = 0;
        while (document.getElementById(`id_form-${formIndex}-server`)) {
            let serverInput = document.getElementById(`id_form-${formIndex}-server`);
            let ipInput = document.getElementById(`id_form-${formIndex}-ip`);
            if (serverInput && ipInput) {
                let ipParent = ipInput.parentElement; // Get the parent element of ipInput
                let ipTd = ipParent.parentElement;
                // add an event listener on the server input that adjusts visibility
                // and value of the ip input (and its parent) 
                serverInput.addEventListener("input", () => {
                    let serverValue = serverInput.value.trim();
                    if (ipParent && ipTd) {
                        if (serverValue.endsWith('.' + this.domain)) {
                            showElement(ipParent); // Show IP field if the condition matches
                            ipTd.classList.add('width-40p');
                        } else {
                            hideElement(ipParent); // Hide IP field otherwise
                            ipTd.classList.remove('width-40p');
                            ipInput.value = ""; // Set the IP value to blank
                        }
                    } else {
                        console.warn("Expected DOM element but did not find it");
                    }
                });
            }
            formIndex++; // Move to the next index
        }

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
     * Handles clicking the 'Add Nameserver' button, showing the form if needed.
     * @param {Event} event - Click event
     */
    handleAddFormClick(event) {
        this.callback = () => {
            // Check if any other edit row is currently visible and hide it
            document.querySelectorAll('tr.edit-row:not(.display-none)').forEach(openEditRow => {
                this.resetEditRowAndFormAndCollapseEditRow(openEditRow);
            });
            if (this.addNameserversForm) {
                // Check if this.addNameserversForm is visible (i.e., does not have 'display-none')
                if (!this.addNameserversForm.classList.contains('display-none')) {
                    this.resetAddNameserversForm();
                }
                // show nameservers form
                showElement(this.addNameserversForm);
            } else {
                this.addAlert("error", "You’ve reached the maximum amount of name server records (13). To add another record, you’ll need to delete one of your saved records.");
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
            // Check if this.addNameserversForm is visible (i.e., does not have 'display-none')
            if (this.addNameserversForm && !this.addNameserversForm.classList.contains('display-none')) {
                this.resetAddNameserversForm();
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
     * Handles clicking a 'Delete' button on an edit row, which hattempts to delete the nameserver
     * after displaying modal and performing check for minimum number of nameservers.
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
     * Handles clicking a 'Delete' button on a readonly row in a kebab, which attempts to delete the nameserver
     * after displaying modal and performing check for minimum number of nameservers.
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
     * Deletes a nameserver row after verifying the minimum required nameservers exist.
     * If there are only two nameservers left, deletion is prevented, and an alert is shown.
     * If deletion proceeds, the input fields are cleared, and the form is submitted.
     * @param {HTMLElement} editRow - The row corresponding to the nameserver being deleted.
     */
    deleteRow(editRow) {
        // Check if at least two nameserver forms exist
        const fourthNameserver = document.getElementById('id_form-3-server'); // This should exist
        // This checks that at least 3 nameservers exist prior to the delete of a row, and if not
        // display an error alert
        if (fourthNameserver) {
            this.callback = () => {
                hideElement(editRow);
                let textInputs = editRow.querySelectorAll("input[type='text']");
                textInputs.forEach(input => {
                    input.value = "";
                });
                const form = editRow.closest("form");
                if (form) form.submit();
            };
            let modalTrigger = document.querySelector('#delete_trigger');
            if (modalTrigger) {
                modalTrigger.click();
            }
        } else {
            this.addAlert("error", "At least two name servers are required. To proceed, add a new name server before removing this name server. If you need help, email us at help@get.gov.");
        }
    }

    /**
     * Handles the click event on the "Cancel" button in the add nameserver form.
     * Resets the form fields and hides the add form section.
     * @param {Event} event - Click event
     */
    handleCancelAddFormClick(event) {
        this.callback = () => {
            this.resetAddNameserversForm();
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
     * Resets the 'Add Nameserver' form by clearing its input fields, removing errors, 
     * and hiding the form to return it to its initial state.
     */
    resetAddNameserversForm() {
        if (this.addNameserversForm) {
            // reset the values set in addNameserversForm
            this.resetInputValuesInElement(this.addNameserversForm);
            // remove errors from the addNameserversForm
            removeErrorsFromElement(this.addNameserversForm);
            // remove errors from the entire form
            removeFormErrors();
            // reset formChanged
            this.resetFormChanged();
            // hide the addNameserversForm
            hideElement(this.addNameserversForm);
        }
    }

    /**
     * Resets all text input fields within the specified DOM element to their initial values.
     * Triggers an 'input' event to ensure any event listeners update accordingly.
     * @param {HTMLElement} domElement - The parent element containing text input fields to be reset.
     */
    resetInputValuesInElement(domElement) {
        const inputEvent = new Event('input');
        let textInputs = domElement.querySelectorAll("input[type='text']");
        textInputs.forEach(input => {
            // Reset input value to its initial stored value
            input.value = input.dataset.initialValue;
            // Dispatch input event to update any event-driven changes
            input.dispatchEvent(inputEvent);
        });
    }

    /**
     * Copies values from the editable row's text inputs into the corresponding
     * readonly row cells, formatting them appropriately.
     * @param {HTMLElement} editRow - The row containing editable input fields.
     * @param {HTMLElement} readOnlyRow - The row where values will be displayed in a non-editable format.
     */
    copyEditRowToReadonlyRow(editRow, readOnlyRow) {
        let textInputs = editRow.querySelectorAll("input[type='text']");
        let tds = readOnlyRow.querySelectorAll("td");
        let updatedText = '';

        // If a server name exists, store its value
        if (textInputs[0]) {
            updatedText = textInputs[0].value;
        }

        // If an IP address exists, append it in parentheses next to the server name
        if (textInputs[1] && textInputs[1].value) {
            updatedText = updatedText + " (" + textInputs[1].value + ")";
        }

        // Assign the formatted text to the first column of the readonly row
        if (tds[0]) {
            tds[0].innerText = updatedText;
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
 * Initializes the NameserverForm when the DOM is fully loaded.
 */
export function initFormNameservers() {
    document.addEventListener('DOMContentLoaded', () => {
        if (document.getElementById('nameserver-add-button')) {
            const nameserverForm = new NameserverForm();
            nameserverForm.init();
        }
    });
}