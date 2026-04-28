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

// when an edit form is open, splice the kebab "More options" in after the form's
// tab order is Edit -> form fields -> Delete -> kebab (instead of the DOM-natural
// Edit -> kebab -> form fields). When closed, normal tab order applies. 
// This is to prevent the user from accidentally tabbing into the kebab menu while 
// trying to navigate form fields, which would be disruptive since the form 
// is still visible in the DOM when open.
export function initDNSRecordTabOrder() {
    const table = document.querySelector("#dnsrecords-table");
    if (!table) return;

    const getOpenRecordId = () => {
        try { return Alpine.$data(table)?.showFormId; } catch (e) { return null; }
    };

    // Resolve the focusable elements that participate in our custom tab order for a record.
    function getRecordElements(recordId) {
        if (!recordId) return null;
        const editBtn = table.querySelector(
            `button[data-action="edit"][data-record-id="${recordId}"]`
        );
        const formRow = document.getElementById(`dnsrecord-edit-row-${recordId}`);
        const kebab = table.querySelector(
            `button[aria-controls="more-actions-dnsrecord-${recordId}"]`
        );
        if (!editBtn || !formRow) return null;
        const formFirst = formRow.querySelector(
            'input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled])'
        );
        const formDelete = formRow.querySelector('[data-action="form-delete"]');
        return { editBtn, formRow, kebab, formFirst, formDelete };
    }

    // Walk the table's focusables in DOM order to find the next visible focusable after `node`.
    // Used so that Tab from the kebab (when a form is open) skips the still-rendered form row
    // and lands on the next record's Edit button instead of cycling back into the form.
    function nextFocusableAfter(node) {
        const selector = 'a[href], a[tabindex="0"], button:not([disabled]), '
            + 'input:not([disabled]):not([type="hidden"]), select:not([disabled]), '
            + 'textarea:not([disabled]), [tabindex="0"]';
        const candidates = table.querySelectorAll(selector);
        let past = false;
        for (const el of candidates) {
            if (past && el.offsetParent !== null) return el;
            if (node === el || node.contains(el)) past = true;
        }
        return null;
    }

    // After Edit is clicked and the form opens, jump focus to the form's first input so the
    // user lands inside the form rather than on the (now-skipped) kebab.
    table.addEventListener('click', (e) => {
        const editBtn = e.target.closest('[data-action="edit"]');
        if (!editBtn) return;
        // The existing editAndCommentButtonListener updates Alpine state synchronously on
        // click; queue a microtask so we observe the post-click state.
        queueMicrotask(() => {
            const recordId = editBtn.dataset.recordId;
            if (getOpenRecordId() !== recordId) return; // form was just toggled closed
            const elems = getRecordElements(recordId);
            elems?.formFirst?.focus();
        });
    });

    // Intercept Tab at the four pivot points to enforce the desired order.
    table.addEventListener('keydown', (e) => {
        if (e.key !== 'Tab') return;
        const recordId = getOpenRecordId();
        if (!recordId) return;
        const elems = getRecordElements(recordId);
        if (!elems) return;

        const t = e.target;

        // Edit -> first form field (Tab forward)
        if (!e.shiftKey && t === elems.editBtn) {
            e.preventDefault();
            elems.formFirst?.focus();
            return;
        }
        // First form field -> Edit (Shift+Tab backward)
        if (e.shiftKey && t === elems.formFirst) {
            e.preventDefault();
            elems.editBtn.focus();
            return;
        }
        // Form Delete -> kebab "More options" (Tab forward)
        if (!e.shiftKey && elems.formDelete && t === elems.formDelete) {
            e.preventDefault();
            elems.kebab?.focus();
            return;
        }
        // Kebab -> Form Delete (Shift+Tab backward, only when form is open)
        if (e.shiftKey && elems.kebab && t === elems.kebab) {
            e.preventDefault();
            elems.formDelete?.focus();
            return;
        }
        // Kebab -> next record's Edit (Tab forward, skipping the still-visible form row)
        if (!e.shiftKey && elems.kebab && t === elems.kebab) {
            e.preventDefault();
            nextFocusableAfter(elems.formRow)?.focus();
            return;
        }
    });
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