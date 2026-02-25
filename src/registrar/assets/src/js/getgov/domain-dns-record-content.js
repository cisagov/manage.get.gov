// Establishes javascript for dynamic content label based on type
export function initDynamicDNSRecordFormFields() { 
    
    const typeField = document.getElementById('id_type');

    if (!typeField) return;

    const config = JSON.parse(
        typeField.dataset.typeConfig || "{}"
    );

    // Getting and cloning the required field asterisk
    const contentLabel = document.querySelector('label[for=id_content]');
    const abbrElement = contentLabel?.querySelector('abbr');
    const abbrClone = abbrElement ? abbrElement.cloneNode(true) : null;

    typeField.addEventListener('change', function (){
        const selectedType = this.value;
        const info = config[selectedType];
        const currentContentLabel = document.querySelector('label[for=id_content]');
        const currentContentHelp = document.getElementById('id_content_helptext');
        
        
        if (info) {
            currentContentLabel.textContent = info.label;
            currentContentHelp.textContent = info.help_text;
        }

        // Appending the asterisk to the label
        currentContentLabel.appendChild(abbrClone);
    });

    // Defensive edge case, if type is pre-selected (ex: submitting with errors)
    if (typeField.value) {
        typeField.dispatchEvent(new Event('change'));
    }
}