import { showElement, hideElement, scrollToElement } from './helpers';

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

    init() {
        this.initializeNameserverFormDisplay();
        this.initializeEventListeners();
    }

    initializeNameserverFormDisplay() {

        const domainName = document.getElementById('id_form-0-domain');
        if (domainName) {
            this.domain = domainName.value;
        }

        // Check if exactly two nameserver forms exist: id_form-1-server is present but id_form-2-server is not
        const secondNameserver = document.getElementById('id_form-1-server');
        const thirdNameserver = document.getElementById('id_form-2-server'); // This should not exist

        // Check if there are error messages in the form (indicated by elements with class 'usa-alert--error')
        const errorMessages = document.querySelectorAll('.usa-alert--error');

        if (this.addNameserversForm && secondNameserver && !thirdNameserver && errorMessages.length > 0) {
            showElement(this.addNameserversForm);
            this.formChanged = true;
        }

        if (this.addNameserversForm && this.addNameserversForm.querySelector('.usa-input--error')) {
            showElement(this.addNameserversForm);
            this.formChanged = true;
        }

        // handle display of table view errors
        // if error exists in an edit-row, make that row show, and readonly row hide
        const formTable = document.querySelector('.usa-table')
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
        // nameserver forms 'smart'
        let formIndex = 0;
        while (document.getElementById(`id_form-${formIndex}-server`)) {
            let serverInput = document.getElementById(`id_form-${formIndex}-server`);
            let ipInput = document.getElementById(`id_form-${formIndex}-ip`);
            if (serverInput && ipInput) {
                let ipParent = ipInput.parentElement; // Get the parent element of ipInput
                serverInput.addEventListener("input", () => {
                    let serverValue = serverInput.value.trim();
                    if (ipParent) {
                        if (serverValue.endsWith('.' + this.domain)) {
                            showElement(ipParent); // Show IP field if the condition matches
                        } else {
                            hideElement(ipParent); // Hide IP field otherwise
                            ipInput.value = ""; // Set the IP value to blank
                        }
                    }
                });
            }
            formIndex++; // Move to the next index
        }

        const unsaved_changes_modal = document.getElementById('unsaved-changes-modal');
        if (unsaved_changes_modal) {
            const submitButton = document.getElementById('unsaved-changes-click-button');
            const closeButton = unsaved_changes_modal.querySelector('.usa-modal__close');
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

    executeCallback() {
        if (this.callback) {
            this.callback();
            this.callback = null;
        } else {
            console.warn("No callback function set.");
        }
    }

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
            //------- Show the confirmation modal
            let modalTrigger = document.querySelector("#unsaved_changes_trigger");
            if (modalTrigger) {
                modalTrigger.click();
            }
        } else {
            this.executeCallback();
        }
    }

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
            //------- Show the confirmation modal
            let modalTrigger = document.querySelector("#unsaved_changes_trigger");
            if (modalTrigger) {
                modalTrigger.click();
            }
        } else {
            this.executeCallback();
        }
    }

    handleDeleteClick(event) {
        let deleteButton = event.target;
        let editRow = deleteButton.closest('tr');
        if (!editRow) {
            console.warn("Expected DOM element but did not find it");
            return;
        }
        this.deleteRow(editRow);
    }

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

    deleteRow(editRow) {
        // Check if at least two nameserver forms exist
        const fourthNameserver = document.getElementById('id_form-3-server'); // This should exist
        if (fourthNameserver) {
            this.callback = () => {
                hideElement(editRow);
                let textInputs = editRow.querySelectorAll("input[type='text']");
                textInputs.forEach(input => {
                    input.value = "";
                });
                document.querySelector("form").submit();
            };
            let modalTrigger = document.querySelector('#delete_trigger');
            if (modalTrigger) {
                modalTrigger.click();
            }
        } else {
            this.addAlert("error", "At least two name servers are required. To proceed, add a new name server before removing this name server. If you need help, email us at help@get.gov.");
        }
    }

    handleCancelAddFormClick(event) {
        this.resetAddNameserversForm();
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
        if (editRow) {
            this.resetEditRowAndFormAndCollapseEditRow(editRow);
        } else {
            console.warn("Expected DOM element but did not find it");
        }
    }

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
        this.removeErrorsFromElement(editRow);
        // remove errors from the entire form
        this.removeFormErrors();
        // reset formChanged
        this.resetFormChanged();
        // hide and show rows as appropriate
        hideElement(editRow);
        showElement(readOnlyRow);
    }

    resetAddNameserversForm() {
        if (this.addNameserversForm) {
            // reset the values set in addNameserversForm
            this.resetInputValuesInElement(this.addNameserversForm);
            // remove errors from the addNameserversForm
            this.removeErrorsFromElement(this.addNameserversForm);
            // remove errors from the entire form
            this.removeFormErrors();
            // reset formChanged
            this.resetFormChanged();
            // hide the addNameserversForm
            hideElement(this.addNameserversForm);
        }
    }

    resetInputValuesInElement(domElement) {
        let textInputs = domElement.querySelectorAll("input[type='text']");
        textInputs.forEach(input => {
            input.value = input.dataset.initialValue;
        })
    }

    copyEditRowToReadonlyRow(editRow, readOnlyRow) {
        let textInputs = editRow.querySelectorAll("input[type='text']");
        let tds = readOnlyRow.querySelectorAll("td");
        let updatedText = '';

        // if server is defined, copy the value to the first td in readOnlyRow
        if (textInputs[0]) {
            updatedText = textInputs[0].value;
            //tds[0].innerText = textInputs[0].value;
        }

        // if ip is defined, copy the value to the second td in readOnlyRow
        if (textInputs[1]) {
            if (textInputs[1].value) {
                updatedText = updatedText + "(" + textInputs[1].value + ")";
            }
            //tds[1].innerText = textInputs[1].value;
        }

        if (tds[0]) {
            tds[0].innerText = updatedText;
        }
    }

    removeErrorsFromElement(domElement) {
        // remove class 'usa-form-group--error' from divs in domElement
        domElement.querySelectorAll("div.usa-form-group--error").forEach(div => {
            div.classList.remove("usa-form-group--error");
        });

        // remove class 'usa-label--error' from labels in domElement
        domElement.querySelectorAll("label.usa-label--error").forEach(label => {
            label.classList.remove("usa-label--error");
        });

        // Remove divs whose id ends with '__error-message' (error message divs)
        domElement.querySelectorAll("div[id$='__error-message']").forEach(errorDiv => {
            errorDiv.remove();
        });

        // remove class 'usa-input--error' from inputs in domElement
        domElement.querySelectorAll("input.usa-input--error").forEach(input => {
            input.classList.remove("usa-input--error");
        });
    }

    removeFormErrors() {
        let formErrorDiv = document.getElementById("form-errors");
        if (formErrorDiv) {
            formErrorDiv.remove();
        }
    }

    resetFormChanged() {
        this.formChanged = false;
    }

    resetAlerts() {
        const mainContent = document.querySelector("main#main-content");
        if (mainContent) {
            mainContent.querySelectorAll(".usa-alert").forEach(alert => alert.remove());
        }
    }
    
    addAlert(level, message) {
        this.resetAlerts();
        
        const mainContent = document.querySelector("main#main-content");
        if (!mainContent) return;
        
        const alertDiv = document.createElement("div");
        alertDiv.className = `usa-alert usa-alert--${level} usa-alert--slim margin-bottom-2`;
        
        const alertBody = document.createElement("div");
        alertBody.className = "usa-alert__body";
        alertBody.textContent = message;
        
        alertDiv.appendChild(alertBody);
        mainContent.insertBefore(alertDiv, mainContent.firstChild);
        scrollToElement("class","usa-alert__body");
    }

}

export function initFormNameservers() {
    document.addEventListener('DOMContentLoaded', () => {

        // Initialize NameserverForm if nameserver-add-button button is present in DOM
        if (document.getElementById('nameserver-add-button')) {
            const nameserverForm = new NameserverForm();
            nameserverForm.init();
        }
    });
}