// Establishes javascript for dynamic content label based on type
export function initDynamicDNSRecordFormFields() {
    const typeField = document.getElementById('id_type');
    const contentField = document.getElementById('id_content');
    const contentLabel = document.querySelector('label[for=id_content]');
    const contentHelp = document.getElementById('id_content_helptext');

    if (!typeField || !contentField) return;

    // Getting and cloning the required field asterisk
    const abbrElement = contentLabel?.querySelector('abbr');
    const abbrClone = abbrElement ? abbrElement.cloneNode(true) : null;

    typeField.addEventListener('change', function (){
        const selectedType = this.value;

        if (selectedType === 'A') {
            typeField.setAttribute('aria-label', 'Record type: A');
            if (contentLabel) contentLabel.textContent = ' IPv4 address ';
            if (contentHelp) contentHelp.textContent = 'Example: 192.0.2.10';
        } else if (selectedType === 'AAAA') {
            typeField.setAttribute('aria-label', 'Record type: Quad A');
            if (contentLabel) contentLabel.textContent = ' IPv6 address ';
            if (contentHelp) contentHelp.textContent = 'Example: 2001:db8::1234:5678';
        } 
        else {
            typeField.removeAttribute('aria-label');
            if (contentLabel) contentLabel.textContent = ' Content ';
            if (contentHelp) contentHelp.textContent = '';
        }
        // Appending the asterisk to the label
        contentLabel.appendChild(abbrClone);
    });

    // Defensive edge case, if type is pre-selected (ex: submitting with errors)
    if (typeField.value) {
        typeField.dispatchEvent(new Event('change'));
    }
}