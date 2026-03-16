// Establishes javascript for dynamic content label based on type

function switchFromInputToTextArea (element) {
        if(!element) return;
        const textArea = document.createElement('textarea');
        textArea.name = element.name;
        textArea.className = 'usa-textarea usa-textarea--medium';
        textArea.setAttribute('aria-label', 'Content')
        textArea.value = element.value
        element.classList.forEach(cls => textArea.classList.add(cls))
       
        
        // Character count
        const charLimit = 2048
        let countText = function () {
           return `${charLimit - textArea.value.length} characters allowed`
        }
        const displayCharCount = document.createElement('div')
        displayCharCount.className = "usa-character-count__status usa-hint"
        displayCharCount.textContent = countText()
        textArea.addEventListener('input', function(){
             displayCharCount.textContent = countText()
             displayCharCount.classList.toggle('usa-character-count__status--invalid', textArea.value.length > charLimit)
        })


        element.replaceWith(textArea)
        textArea.insertAdjacentElement('afterend', displayCharCount)
}

export function initDynamicDNSRecordFormFields() { 
    
    const typeField = document.getElementById('id_type');

    if (!typeField) return;

    const config = JSON.parse(
        typeField.dataset.typeConfig || "{}"
    );

    const textAreaContent = document.querySelectorAll('.content-field-wrapper-txt');

    // For the edit rows to update from input to text area
    textAreaContent.forEach( input => {
                let currentInput = input.querySelector('input');
                if(currentInput){
                    switchFromInputToTextArea(currentInput)
                }
    })
  


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
            contentHelp && (contentHelp.textContent = info.help_text)
        }
       
        if(selectedType == "TXT"){
            // Swap input type to text area
            let input = document.querySelector(".content-field-wrapper-txt input")
            input && switchFromInputToTextArea(input)
        }
        

        // Appending the asterisk to the label
        contentLabel.appendChild(abbrClone);


      
    });
    
    // Defensive edge case, if type is pre-selected (ex: submitting with errors)
    if (typeField.value) {
        typeField.dispatchEvent(new Event('change'));
    }
}