import { showElement, hideElement } from './helpers';

function handleAddFormClick(e) {
    let nameserversForm = document.querySelector('.nameservers-form');
    if (!nameserversForm) {
        console.warn('Expected DOM element but did not find it');
        return; 
    }
    
    showElement(nameserversForm);
    
    if (e?.target) {
        hideElement(e.target);
    }
}

function handleEditClick(e) {
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

function handleCancelClick(e) {
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

export function initFormNameservers() {
    const addButton = document.getElementById('nameserver-add-form');
    if (!addButton) return;

    addButton.addEventListener('click', handleAddFormClick);

    const editButtons = document.querySelectorAll('.nameserver-edit');
    editButtons.forEach(editButton => {
        editButton.addEventListener('click', handleEditClick);
    });

    const cancelButtons = document.querySelectorAll('.nameserver-cancel');
    cancelButtons.forEach(cancelButton => {
        cancelButton.addEventListener('click', handleCancelClick);
    })
}
