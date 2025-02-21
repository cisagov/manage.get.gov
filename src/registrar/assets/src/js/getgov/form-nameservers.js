import { showElement, hideElement } from './helpers';

function handleAddForm(e) {
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

export function initFormNameservers() {
    const addButton = document.getElementById('nameserver-add-form');
    if (!addButton) return;

    addButton.addEventListener('click', handleAddForm);
}
