// Establishes javascript for dynamic content label based on type

function getCharCountText (charLimit, textArea) {
    const charactersLeft = charLimit - textArea.value.length;
    if (charactersLeft >= 0) {
      const characters = `character${charactersLeft === 1 ? '' : 's'}`;
      return `${charactersLeft} ${characters} left`;
    } else {
      const characters = `character${Math.abs(charactersLeft) === 1 ? '' : 's'}`;
      return `${Math.abs(charactersLeft)} ${characters} over limit`;
    }
  };

function createCharacterCountDiv(charLimit, textArea) {

  const displayCharCount = document.createElement('div');
  displayCharCount.className = 'usa-character-count__status usa-hint';
  displayCharCount.textContent = getCharCountText(charLimit, textArea);
  textArea.addEventListener('input', function () {
    displayCharCount.textContent = getCharCountText(charLimit, textArea);
    displayCharCount.classList.toggle(
      'usa-character-count__status--invalid',
      textArea.value.length > charLimit
    );
  });
  return displayCharCount;
}

function switchFromInputToTextArea (element) {
        if(!element) return;
        const textArea = document.createElement('textarea');
        textArea.name = element.name;
        textArea.className = 'usa-textarea usa-textarea--medium';
        textArea.required = true
        textArea.id = element.id
        textArea.value = element.value
        element.classList.forEach(cls => textArea.classList.add(cls))
       
        
        // Character count
        const charLimit = 2048
        const displayCharCount = createCharacterCountDiv(charLimit, textArea)

        element.replaceWith(textArea)
        textArea.insertAdjacentElement('afterend', displayCharCount)
}


export function editAndCommentButtonListener (){
        const table = document.querySelector("#dnsrecords-table");
        if(!table) return;

        table.addEventListener('click', function(e) {
            const editBtn =  e.target.closest('[data-action="edit"]')
            const commentBtn = e.target.closest('[data-action="comment"]')
            if(!editBtn && !commentBtn) return;
            
            const recordId = (editBtn || commentBtn).dataset.recordId
            const alpineData = Alpine.$data(table)
            
            if(editBtn){
                const idx = alpineData.openComments.indexOf(recordId)
                if(idx > -1) alpineData.openComments.splice(idx,1);
                alpineData.showFormId = alpineData.showFormId === recordId ? null : recordId;
            }

            if(commentBtn){
                if(alpineData.showFormId === recordId) alpineData.showFormId = null;
                const idx = alpineData.openComments.indexOf(recordId);
                idx > -1 ? alpineData.openComments.splice(idx,1) : alpineData.openComments.push(recordId)

            }
        
        })
}

export function commentCharacterEventListener(){
    function helperEventListener (element){
        if(!element){
            return;
        }
        const commentText = element.querySelector('.comment-character-count')
        const commentTextArea = element.querySelector('textarea[name="comment"]')
        commentTextArea.addEventListener('input', function () {
            commentText.textContent = getCharCountText(100, commentTextArea);
            commentText.classList.toggle(
              'usa-character-count__status--invalid',
              commentTextArea.value.length > 100
          );
       });

    }
    let rows = document.querySelectorAll('[id^="dnsrecord-edit-row-"]')
    const form = document.getElementById('dnsrecords-form-container')

    rows && rows.forEach(row => {
       helperEventListener(row)
    })

    helperEventListener(form)
}

export function initDynamicDNSRecordFormFields() { 
    const typeField = document.getElementById('id_type');

    if (!typeField) return;

    const config = JSON.parse(
        typeField.dataset.typeConfig || "{}"
    )
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
          console.log("HELLO")
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
            setTimeout(()=>{
            let input = document.querySelector(".content-field-wrapper-txt input")
            input && switchFromInputToTextArea(input)
            }, 0
            )
        }
        

        // Appending the asterisk to the label
        contentLabel.appendChild(abbrClone);


    });
    // Defensive edge case, if type is pre-selected (ex: submitting with errors)
    if (typeField.value) {
        typeField.dispatchEvent(new Event('change'));
    }

}