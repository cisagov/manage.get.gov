// Establishes javascript for dynamic content label based on type

function switchFromInputToTextArea (element) {
        const ta = document.createElement('textarea');
        ta.name = element.name;
        ta.className = 'usa-textarea usa-textarea--medium';
        element.replaceWith(ta)
}


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

    const textAreaContent = document.querySelectorAll('.content-field-wrapper-txt');

    if(textAreaContent){
        textAreaContent.forEach( input => {
            let currentInput = input.querySelector('input');
            if(currentInput){
                   switchFromInputToTextArea(currentInput)
            }
        })
    }
  

    typeField.addEventListener('change', function (){
        const selectedType = this.value;
        const info = config[selectedType];
     
        if (info) {
            contentLabel.textContent = info.label;
            contentHelp.textContent = info.help_text;
        }

        let container = document.getElementById("record-type-container")
        if(selectedType === "TXT" && container) {
             const txtForm = document.getElementById("txt-form-template")
             container.innerHTML = txtForm.innerHTML
        }
        else{
            const baseForm = document.getElementById("base-form-template")
            container.innerHTML = baseForm.innerHTML
        }
        // Appending the asterisk to the label
        contentLabel.appendChild(abbrClone);
      
    });

    // Defensive edge case, if type is pre-selected (ex: submitting with errors)
    if (typeField.value) {
        typeField.dispatchEvent(new Event('change'));
    }
}