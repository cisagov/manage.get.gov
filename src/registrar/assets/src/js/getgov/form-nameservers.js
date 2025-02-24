import { showElement, hideElement } from './helpers';

export class NameserverForm {
    constructor() {
        this.addNameserverButton = document.getElementById('nameserver-add-form');
        this.nameserversForm = document.querySelector('.nameservers-form');

        // Bind event handlers to maintain 'this' context
        this.handleAddFormClick = this.handleAddFormClick.bind(this);
        this.handleEditClick = this.handleEditClick.bind(this);
        this.handleCancelClick = this.handleCancelClick.bind(this);
    }

    init() {
        this.initializeNameserverFormDisplay();
        this.initializeEventListeners();
    }

    initializeNameserverFormDisplay() {
        // Check if exactly two nameserver forms exist: id_form-1-server is present but id_form-2-server is not
        const secondNameserver = document.getElementById('id_form-1-server');
        const thirdNameserver = document.getElementById('id_form-2-server'); // This should not exist

        // Check if there are error messages in the form (indicated by elements with class 'usa-alert--error')
        const errorMessages = document.querySelectorAll('.usa-alert--error');

        if (secondNameserver && !thirdNameserver && errorMessages.length > 0) {
            showElement(this.nameserversForm);
            hideElement(this.addNameserverButton);
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
    }

    handleAddFormClick(event) {
        showElement(this.nameserversForm);
        hideElement(this.addNameserverButton);
    }

    handleEditClick(e) {
        let editButton = e.target;
        let readOnlyRow = editButton.closest('tr'); // Find the closest row
        let editRow = readOnlyRow.nextElementSibling; // Get the next row

        if (!editRow || !readOnlyRow) {
            console.warn("Expected DOM element but did not find it");
            return;
        }

        // Check if any other edit row is currently visible and hide it
        document.querySelectorAll('tr.edit-row:not(.display-none)').forEach(openEditRow => {
            let correspondingReadOnlyRow = openEditRow.previousElementSibling;
            hideElement(openEditRow);
            showElement(correspondingReadOnlyRow);
        });

        hideElement(readOnlyRow);
        showElement(editRow);
    }

    handleCancelClick(e) {
        let cancelButton = e.target;
        let editRow = cancelButton.closest('tr'); // Find the closest row
        let readOnlyRow = editRow.previousElementSibling; // Get the next row

        if (!editRow || !readOnlyRow) {
            console.warn("Expected DOM element but did not find it");
            return;
        }

        hideElement(editRow);
        showElement(readOnlyRow);
    }

}

export function initFormNameservers() {
    document.addEventListener('DOMContentLoaded', () => {

        // Initialize NameserverForm if nameserver-add-form button is present in DOM
        if (document.getElementById('nameserver-add-form')) {
            const nameserverForm = new NameserverForm();
            nameserverForm.init();
        }
    });
}