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
    const trimmedValue = textArea.value.trim().length
    displayCharCount.textContent = getCharCountText(charLimit, trimmedValue);
    displayCharCount.classList.toggle(
      'usa-character-count__status--invalid',
      trimmedValue > charLimit
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

        const charLimit = 4080
        const displayCharCount = createCharacterCountDiv(charLimit, textArea)

        element.replaceWith(textArea)
        textArea.insertAdjacentElement('afterend', displayCharCount)
}

function clearRecordForm(root){
    const form = root || document.getElementById("dnsrecords-form-container")
    if(!form) return;

    // remove error styling from inputs and labels
    const inputs = form.querySelectorAll('input:not([type="hidden"]), textarea')
    inputs.forEach(input =>{
        input.classList.remove("usa-input--error")
    })
    const labels = form.querySelectorAll('label')
    labels.forEach( label => label.classList.remove("usa-label--error"))

    // remove error messages in line and top-level error messages
    form.querySelectorAll('.usa-error-message').forEach( el =>{ el.remove()})
    const alertMessagesContainer = document.getElementById('messages-container')
    alertMessagesContainer.querySelectorAll('.usa-alert').forEach(el => el.remove())

    // Reset the comment field and its character count
    document.getElementById('id_comment').value = ''
    const commentStatus =  document.getElementById('dnsrecords-form-container-comment--status')
    commentStatus.classList.remove("usa-character-count__status--invalid")
     // Character count is hardcoded for now if/when the model is updated with the current maxlength
    commentStatus.textContent = getCharCountText(100, 0)
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

// Tab-order routing for the DNS records table (#4804).
// When a form is open, route Tab to walk:
//   Edit → form fields → Delete → kebab → next row's Edit
// Shift+Tab does the reverse. When closed, native order is fine.
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

    // Find the next record row's Edit button, skipping edit/comment rows between records.
    // First focusable on the next record row. The comment toggle button
    // (only rendered when that record has a comment) sits before the Edit
    // button in DOM, so prefer it when present so screen-reader / keyboard
    // users don't skip past the comment indicator.
    function nextRecordEntryAfter(recordId) {
        let row = document.getElementById(`dnsrecord-row-${recordId}`);
        while (row?.nextElementSibling) {
            row = row.nextElementSibling;
            if (!row.id?.startsWith('dnsrecord-row-')) continue;
            return row.querySelector('button[data-action="comment"], button[data-action="edit"]');
        }
        return null;
    }

    function nextFocusableAfterElement(node) {
        const selector = 'a[href], a[tabindex="0"], button:not([disabled]), '
            + 'input:not([disabled]):not([type="hidden"]), select:not([disabled]), '
            + 'textarea:not([disabled]), [tabindex="0"]';
        const candidates = document.querySelectorAll(selector);
        let past = false;
        for (const el of candidates) {
            if (past && el.offsetParent !== null) return el;
            if (node === el || node.contains(el)) past = true;
        }
        return null;
    }

    // Defer focus calls until Alpine has flushed x-show — otherwise .focus()
    // hits a still-hidden element and silently no-ops. Alpine.nextTick
    // handles that; rAF is a safety net for headless Chromium.
    function deferFocus(fn) {
        if (window.Alpine?.nextTick) {
            window.Alpine.nextTick(() => requestAnimationFrame(fn));
        } else {
            requestAnimationFrame(fn);
        }
    }

    table.addEventListener('click', (e) => {
        const trigger = e.target.closest('[data-action="edit"], [data-action="form-cancel"]');
        if (!trigger) return;
        const recordId = trigger.dataset.recordId;
        deferFocus(() => {
            const elems = getRecordElements(recordId);
            if (!elems) return;
            const isOpen = getOpenRecordId() === recordId;
            (isOpen ? elems.formFirst : elems.editBtn)?.focus();
        });
    });

    // Intercept Tab to enforce the desired order. We always reroute Tab from the Edit
    // button explicitly (rather than relying on natural DOM order) because the row's
    // mobile-only Delete and the USWDS accordion can intercept Tab in ways that vary
    // by viewport and post-HTMX state.
    table.addEventListener('keydown', (e) => {
        if (e.key !== 'Tab') return;

        const t = e.target;

        // Tab/Shift+Tab from any record's Edit button: route based on that record's
        // form state, regardless of whether any other form is open.
        const editBtn = t.closest?.('[data-action="edit"]');
        if (editBtn === t) {
            const rid = editBtn.dataset.recordId;
            const r = getRecordElements(rid);
            if (!r) return;
            const isOpen = getOpenRecordId() === rid;
            if (!e.shiftKey) {
                // Edit -> first form field (open) | kebab (closed)
                e.preventDefault();
                (isOpen ? r.formFirst : r.kebab)?.focus();
            }
            // Shift+Tab from Edit: let natural DOM order go to the previous focusable.
            return;
        }

        // The remaining rules apply only while a form is open.
        const recordId = getOpenRecordId();
        if (!recordId) return;
        const elems = getRecordElements(recordId);
        if (!elems) return;

        const kebabMenu = elems.kebab
            ? document.getElementById(elems.kebab.getAttribute('aria-controls'))
            : null;
        const isKebabFocus = elems.kebab && (t === elems.kebab || kebabMenu?.contains(t));
        const nextRecordEntry = nextRecordEntryAfter(recordId);

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
        // Kebab -> Form Delete (Shift+Tab backward, form open)
        if (e.shiftKey && isKebabFocus) {
            e.preventDefault();
            elems.formDelete?.focus();
            return;
        }
        // Next record's Edit -> kebab (Shift+Tab backward, form open)
        if (e.shiftKey && elems.kebab && t === nextRecordEntry) {
            e.preventDefault();
            elems.kebab.focus();
            return;
        }
        // Kebab -> next record's Edit / out of table (Tab forward, form open — skip the
        // visible form row that would otherwise be next in DOM order).
        if (!e.shiftKey && isKebabFocus) {
            const destination = nextRecordEntry || nextFocusableAfterElement(table);
            if (!destination) return;
            e.preventDefault();
            destination.focus();
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

    typeField.addEventListener('change', function (e){
        // e.isTrusted ensures that this only fires when a user select a new type.
        if(e.isTrusted){
            clearRecordForm()
        }

        const selectedType = this.value;
        const info = config[selectedType];

        // Defer to the next tick so Alpine.js has time to swap the form sub-template
        // (x-if base/MX/TXT) before we query the freshly-mounted label and helptext.
        // Without this, we update DOM nodes that are about to be removed, and the new
        // template renders with the default server-rendered label/help text.
        setTimeout(() => {
            const contentLabel = document.querySelector('label[for=id_content]');
            if (!contentLabel) return;

            // Preserve the required field asterisk while overwriting label text
            const abbrElement = contentLabel.querySelector('abbr');
            const abbrClone = abbrElement ? abbrElement.cloneNode(true) : null;

            if (info) {
                contentLabel.textContent = info.label;
                const contentHelp = document.getElementById('id_content_helptext');
                if (contentHelp) contentHelp.textContent = info.help_text;
            }

            if (selectedType === "TXT") {
                const input = document.querySelector(".content-field-wrapper-txt input");
                if (input) switchFromInputToTextArea(input);
            }

            if (abbrClone) contentLabel.appendChild(abbrClone);
        }, 0);
    });
    // Defensive edge case, if type is pre-selected (ex: submitting with errors)
    if (typeField.value) {
        typeField.dispatchEvent(new Event('change'));
    }

    // clearForm when a user hits the cancel button on the dns record form and table
    document.querySelectorAll(".js-dnsrecord-cancel-button").forEach( button => {
        const formInRow = button.closest('form')
        button.addEventListener('click',() => clearRecordForm(formInRow))
        }
    )
}
