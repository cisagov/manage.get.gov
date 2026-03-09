// Establishes javascript for dynamic content label based on type
export function initDynamicDNSRecordFormFields() { 
    console.log('Init started');
    console.log('config: ', config)
    
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
        
            const current = document.getElementById('id_content');
            if (info.use_textarea && current.tagName === 'INPUT') {
                const ta = document.createElement('textarea');

                ta.id = current.id;
                ta.name = current.name;
                ta.className = 'usa-textarea';
                current.replaceWith(ta);
            } else if (!info.use_textarea && current.tagName === 'TEXTAREA') {
                const inp = document.createElement('input');
                
                inp.type = 'text';
                inp.id = current.id;
                inp.name = current.name;
                inp.className = 'usa-input';
                current.replaceWith(inp);
            }

            console.log(typeField.dataset.typeConfig);
        
        }
        
        // Appending the asterisk to the label
        contentLabel.appendChild(abbrClone);
    });

    // Defensive edge case, if type is pre-selected (ex: submitting with errors)
    if (typeField.value) {
        typeField.dispatchEvent(new Event('change'));
    }
}