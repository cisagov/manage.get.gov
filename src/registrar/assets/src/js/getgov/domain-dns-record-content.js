function adjustedCharCount(charLength){
    // strip out surrounding double quotes and string splitting used for RFC compliance.
        // They should not be included in the character count displayed to to user.
        const adjustedValue =textArea.value.split('" "').join()
        if (adjustedValue.startsWith('"') && adjustedValue.endsWith('"'))
            adjustedValue = adjustedValue.slice(1, -1);
}
// Establishes javascript for dynamic content label based on type
function getCharCountText (charLimit, charLength) {
    let finalString = "";

    if(charLength == 0){
        finalString = `${charLimit} characters allowed`
    }
    else{
        const charactersLeft = Math.abs(charLimit - charLength);
        const remainingText =  charLimit < charLength ? "over limit" : "left";
        const characters =`character${charactersLeft === 1 ? '' : 's'}`;
        finalString = `${charactersLeft} ${characters} ${remainingText}`
    }

    return finalString;
  };

function createCharacterCountDiv(charLimit, textArea) {


  const displayCharCount = document.createElement('div');
  displayCharCount.className = 'usa-character-count__status usa-hint';
  displayCharCount.textContent = getCharCountText(charLimit, textArea.value.length)


  displayCharCount.id = `${textArea.id}-content--status`
  displayCharCount.setAttribute('aria-live', 'polite')


  textArea.addEventListener('input', function () {
    displayCharCount.textContent = getCharCountText(charLimit, textArea.value.length);
    displayCharCount.classList.toggle(
      'usa-character-count__status--invalid',
      textArea.value.length > charLimit
    );
  });
  textArea.setAttribute('aria-describedby', displayCharCount.id)
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
        const charLimit = 4080
        let getCharCountText = function () {
           return `${charLimit - textArea.value.length} characters allowed`
        }
        const displayCharCount = document.createElement('div')
        displayCharCount.className = "usa-character-count__status usa-hint"
        displayCharCount.textContent = getCharCountText()
        textArea.addEventListener('input', function(){
             displayCharCount.textContent = getCharCountText()
             displayCharCount.classList.toggle('usa-character-count__status--invalid', textArea.value.length > charLimit)
        })


        element.replaceWith(textArea)
        textArea.insertAdjacentElement('afterend', displayCharCount)
}


export function editAndCommentButtonListener (){
        const table = document.querySelector("#dnsrecords-table");
        if(!table) return;

        table.addEventListener('click', function(e) {
            const editBtn =  e.target.closest('[data-action="edit"')
            const commenttBtn = e.target.closest('[data-action="comment"')
            if(!editBtn && !commenttBtn) return;

            const recordId = (editBtn || commenttBtn).dataset.recordId
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

    // event listener to update the char count text
    const commentCharLimit = 100
    function helperEventListener (element){
        if(!element){
            return;
        }
        const commentTextStatus = element.querySelector('.comment-character-count')
        const commentTextArea = element.querySelector('textarea[id$="_comment"]')
        commentTextArea.addEventListener('input', function () {
            commentTextStatus.textContent = getCharCountText(commentCharLimit, commentTextArea.value.length);
            commentTextStatus.classList.toggle(
              'usa-character-count__status--invalid',
              commentTextArea.value.length > commentCharLimit
          );
       });
        commentTextStatus.id = `${element.id}-comment--status`
        commentTextStatus.setAttribute('aria-live', 'polite')
        commentTextArea.setAttribute('aria-describedby', commentTextStatus.id)
    }


    let rows = document.querySelectorAll('tr[id^="dnsrecord-edit-row-"]')
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
            // Utilized set time out for Firefox loading engine to grab the input after dom content loads
            setTimeout(()=>{
            let input = document.querySelector(".content-field-wrapper-txt input")
            input && switchFromInputToTextArea(input)
            }, 0)
        }


        // Appending the asterisk to the label
        contentLabel.appendChild(abbrClone);



    });

    // Defensive edge case, if type is pre-selected (ex: submitting with errors)
    if (typeField.value) {
        typeField.dispatchEvent(new Event('change'));
    }

}