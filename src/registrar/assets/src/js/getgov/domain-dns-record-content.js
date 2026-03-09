// Establishes javascript for dynamic content label based on type
export function initDynamicDNSRecordFormFields() { 
    const typeField = document.getElementById('id_type');

    if (!typeField) return;

    const config = JSON.parse(
        typeField.dataset.typeConfig || "{}"
    );

    const contentLabel = document.querySelector('label[for=id_content]');
    const contentHelp = document.getElementById('id_content_helptext');
    
    // Getting and cloning the required field asterisk
    const abbrElement = contentLabel?.querySelector('abbr');
    const abbrClone = abbrElement ? abbrElement.cloneNode(true) : null;

    typeField.addEventListener('change', function (){
        const selectedType = this.value;
        const info = config[selectedType];
        
        
        if (info) {
            contentLabel.textContent = info.label;
            contentHelp.textContent = info.help_text;
        }

        // Appending the asterisk to the label
        contentLabel.appendChild(abbrClone);
    });

    // Defensive edge case, if type is pre-selected (ex: submitting with errors)
    if (typeField.value) {
        typeField.dispatchEvent(new Event('change'));
    }
}