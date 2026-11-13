// Submit buttons data selector and the shared live region Constants.
const BUSY_BUTTON_SELECTOR = '[data-busy-button]';
const STATUS_REGION_ID = 'processing-request-status';

// Busy button state default label if not explicit labels.
const BUSY_BUTTON_LABEL_DEFAULT = 'Processing';
const STATUS_REGION_TEXT = 'Processing your request';
/**
 * A function that sets submit buttons to a busy (spinner) state and prevent double-clicks.
 * 
 * Find each form with a [BUSY_BUTTON_SELECTOR] submit button in the page, 
 * then add event listeners on submit and pageshow to handle busy state.
 * 
 */
export function initFormBusyButtons() {
    const buttons = document.querySelectorAll(BUSY_BUTTON_SELECTOR);
    const forms = new Set();

    buttons.forEach((button) => {
        if (button.form) {
            forms.add(button.form);
        }
    });

    forms.forEach((form) => {
        form.addEventListener('submit', (event) => {
            if (form.dataset.processingRequest === 'true') {
                event.preventDefault();
                return;
            }
            const button = event.submitter?.matches(BUSY_BUTTON_SELECTOR)
                ? event.submitter
                : form.querySelector(BUSY_BUTTON_SELECTOR);
            if (!button) {
                return;
            }
            form.dataset.processingRequest = 'true';
            setBusyButton(button);
        });
    });

    // Clear stale busy state if browser restores this page from its back-forward cache.
    window.addEventListener('pageshow', (event) => {
        if (!event.persisted) {
            return;
        }
        buttons.forEach(resetButton);
        forms.forEach((form) => {
            delete form.dataset.processingRequest;
        });
    });
}

function setBusyButton(button) {
    if (!button || button.dataset.processingRequest === 'true') {
        return;
    }
    const idleLabel = button.textContent.trim();

    if (!button.dataset.idleLabel) {
        button.dataset.idleLabel = idleLabel;
    }

    const busyLabel = (button.dataset.busyButton || BUSY_BUTTON_LABEL_DEFAULT);
    
    button.textContent = `${busyLabel}...`;
    button.dataset.processingRequest = 'true';
    button.setAttribute('aria-disabled', 'true');

    const statusRegion = document.getElementById(STATUS_REGION_ID);
    if (statusRegion) {
        statusRegion.textContent = STATUS_REGION_TEXT;
    }
}

function resetButton(button) {
    if (!button) {
        return;
    }
    if (button.dataset.idleLabel) {
        button.textContent = button.dataset.idleLabel;
    }
    button.removeAttribute('aria-disabled');
    delete button.dataset.processingRequest;
    delete button.dataset.idleLabel;

    const statusRegion = document.getElementById(STATUS_REGION_ID);
    if (statusRegion) {
        statusRegion.textContent = '';
    }
}