// Establishes javascript for dynamic content label based on type

function switchFromInputToTextArea (element) {
        const ta = document.createElement('textarea');
        ta.name = element.name;
        ta.className = 'usa-textarea usa-textarea--medium';
        ta.setAttribute('aria-label', 'Content')
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


    const textAreaContent = document.querySelectorAll('.content-field-wrapper-txt');

    if(textAreaContent){
        // For the edit rows to update from input to text area
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
        const contentLabel = document.querySelector('label[for=id_content]');
        const contentHelp = document.getElementById('id_content_helptext');
        
        // Getting and cloning the required field asterisk
        const abbrElement = contentLabel?.querySelector('abbr');
        const abbrClone = abbrElement ? abbrElement.cloneNode(true) : null;
     
        if (info) { 
            contentLabel.textContent = info.label;
            contentHelp.textContent = info.help_text;
        }
       
        if(selectedType == "TXT"){
            // set delay for alpine to render the form to grab the input to change it
            setTimeout(()=> {
                let input = document.querySelector(".content-field-wrapper-txt input")
                switchFromInputToTextArea(input)
            }, 10)
               
        }
        

        // Appending the asterisk to the label
        contentLabel.appendChild(abbrClone);
      
    });
    
    // Defensive edge case, if type is pre-selected (ex: submitting with errors)
    if (typeField.value) {
        typeField.dispatchEvent(new Event('change'));
    }
}