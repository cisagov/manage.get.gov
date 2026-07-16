import { EditFormSwitcher, RecordSelectTypeSwitcher } from "./domain-dns-form-switcher";

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
        textArea.defaultValue = element.value
        element.classList.forEach(cls => textArea.classList.add(cls))

        const charLimit = 4080
        const displayCharCount = createCharacterCountDiv(charLimit, textArea)

        element.replaceWith(textArea)
        textArea.insertAdjacentElement('afterend', displayCharCount)
}

// Validation errors produces an inline error and a top-level error banner, Clear both.
function clearRecordErrors(scope){
    if(scope){
        scope.querySelectorAll(".usa-error-message").forEach(el => el.remove());
        scope.querySelectorAll(".usa-input--error").forEach(el => el.classList.remove("usa-input--error"));
        scope.querySelectorAll(".usa-label--error").forEach(el => el.classList.remove("usa-label--error"));
    }
    document.getElementById("messages-container")?.querySelectorAll(".usa-alert--error").forEach(el => el.remove());
}

function clearRecordForm(scope){
    const form = scope || document.getElementById("dnsrecords-form-container")
    if(!form) return;

    clearRecordErrors(form)

    // Reset the comment field and its character count
    document.getElementById('id_comment').value = ''
    const commentStatus =  document.getElementById('dnsrecords-form-container-comment--status')
    commentStatus.classList.remove("usa-character-count__status--invalid")
     // Character count is hardcoded for now if/when the model is updated with the current maxlength
    commentStatus.textContent = getCharCountText(100, 0)
}


// DOM ids/selectors for a cancel target, keyed off the add vs edit row id
const refsFor = (req) =>{
    if(req.type === "edit"){
        return  {
        form: `#dnsrecord-edit-form-${req.recordId}`,
        cancelButtonId: `dnsrecord-edit-cancel-button-${req.recordId}`,
        focusId: `dnsrecord-edit-button-${req.recordId}`,
        }
    }
    else {
        const refDict =  
            { 
            form: "#form-container", 
            cancelButtonId: "dnsrecord-add-cancel-button",
            focusId: "add-dnsrecord-button" 
        };
        
        if(req.isRecordType){
            refDict.focusId = "id_type"
        }

        return refDict;
    }

}


// Replace with a fresh server copy, removes client-side edits and errors
const refreshForm = (selector, url) =>
    window.htmx?.ajax("GET", url, { target: selector, select: selector, swap: "outerHTML" });

function openCancelModal(opener){
    document.getElementById("open-cancel-add-dnsrecord-modal")?.click();
    document.getElementById("toggle-cancel-add-dnsrecord")?.setAttribute("data-opener", opener);
}

// fields, reused for both Add and Edit forms.
const FIELD_SELECTOR = 'input:not([type="hidden"]), textarea';

// Add: any non-empty field (type dropdown excluded) is unsaved. Edit: any field differing from its original.
function formHasUnsavedChanges(form, isEditForm){
    if(!form) return false;
    // A failed save uses the rejected values as the fields, so treat a visible error
    // as unsaved so cancel still confirms and resets.
    if(form.querySelector(".usa-error-message")) return true;
    return Array.from(form.querySelectorAll(`${FIELD_SELECTOR}, select`)).some(el => {
        if(el.id === "id_type") return false;
        if(el.tagName === "SELECT") return Array.from(el.options).some(o => o.selected !== o.defaultSelected);
        if(!isEditForm) return el.value.trim() !== "";
        // Django prepends a newline to <textarea> that .value drops but .defaultValue keeps; strip it before comparing.
        const original = el.tagName === "TEXTAREA" ? el.defaultValue.replace(/^\n/, "") : el.defaultValue;
        return el.value !== original;
    });
}

const teardownForm = (switcher) => {
    const req = switcher.pending;
    const refs = refsFor(req);
    const form = document.querySelector(refs.form);
    if(req.type === "edit"){
        if(form){
            // After a failed save the row holds the rejected values; clear both errors inline and top,
            // then re-fetch the row for the real saved values.
            if(form.querySelector(".usa-error-message")){
                clearRecordErrors(form);
                refreshForm(refs.form, form.getAttribute("hx-post"));
            } else if(req.hasUnsavedChanges){
                form.reset();
            }
        }
    } else {
        // A reopened Add form must be blank. Capture hadError before clearRecordForm strips it,
        // then re-fetch a clean form on error, otherwise blank the live fields in place.
        const hadError = !!form?.querySelector(".usa-error-message");
        clearRecordForm(form);
        if(hadError){
            refreshForm(refs.form, form.getAttribute("hx-post"));
        } else {
            form?.querySelectorAll(FIELD_SELECTOR).forEach(el => { el.value = ""; });
            const typeField = document.getElementById("id_type");
            if(typeField) typeField.value = "";
        }
    }
};


const onCancel = (switcher) => {
        const req = switcher.pending;
        const refs = refsFor(req);
        const form = document.querySelector(refs.form);
        req.hasUnsavedChanges = formHasUnsavedChanges(form, req.type === "edit");
        if(req.hasUnsavedChanges){
            openCancelModal(refs.cancelButtonId);
        } else {
            teardownForm(switcher);
            switcher.switchForm();
            document.getElementById(refs.focusId)?.focus();
        }
};


const editButtonEventListener = (switcher)=>{
    const table = document.querySelector("#dnsrecords-table");
    if(!table) return;

    const alpineData = switcher.getAlpineData();
    
    table.addEventListener('click', (e) => {
            const editBtn =  e.target.closest('[data-action="edit"]')
            const commentBtn = e.target.closest('[data-action="comment"]')
            if(!editBtn && !commentBtn) return;

            const recordId = (editBtn || commentBtn).dataset.recordId

            if(editBtn){
                const idx = alpineData.openComments.indexOf(recordId)
                if(idx > -1) alpineData.openComments.splice(idx,1);
        
                switcher.setTarget(recordId)
                if(alpineData.showFormId == null){
                    switcher.switchForm()
                }
                else{
                    switcher.attemptOpen(recordId);
                    onCancel(switcher); 
                }              
            }

            if(commentBtn){
                if(alpineData.showFormId === recordId) switcher.switchForm(null);
                const idx = alpineData.openComments.indexOf(recordId);
                idx > -1 ? alpineData.openComments.splice(idx,1) : alpineData.openComments.push(recordId)
            }

        }
    )
}

export function initDNSRecordCancelModal(){
    const container = document.getElementById("dnsrecords-form-container");
    const confirmButton = document.getElementById("cancel-add-dnsrecord-confirm");
    if(!container || !confirmButton) return;
    
    const editFormSwitcher = new EditFormSwitcher(container);
    
    container.addEventListener("click", (e) => {
        if(!e.target.closest(".js-dnsrecord-add-cancel")) return;
        editFormSwitcher.setPending(
            {
                type: "add"
            }
        )
        onCancel(editFormSwitcher);
    });

    // Delegated on the table so it survives the htmx swaps that re-render Edit rows.
    document.querySelector("#dnsrecords-table")?.addEventListener("click", (e) => {
        const btn = e.target.closest(".js-dnsrecord-edit-cancel");
        if(!btn) return;
        editFormSwitcher.setPending(
            { type: "edit", recordId: btn.dataset.recordId }
        );
        onCancel(editFormSwitcher);
    });
    
    const getSwitcher = ()=>{
            if(recordTypeSwitcher.pending){
                return recordTypeSwitcher;
            }
            if(editFormSwitcher.pending){
                return editFormSwitcher;
            }

            return;
    }

    const modalEl = document.getElementById("toggle-cancel-add-dnsrecord");
    const cancelButton = modalEl?.querySelector("[data-close-modal]");
    const selector = document.querySelector("#select-record-type select");

    confirmButton.addEventListener("click", () => {

       const switcher = getSwitcher()
       if(!switcher){
        return;
       }

        teardownForm(
            switcher,
            container
        );

        const reqForTarget = {
            type: switcher.target > 0 && !switcher.isRecordType ? "edit" : "add",
            recordId: switcher.target,
            isRecordType: switcher.isRecordType
        }

        modalEl?.setAttribute("data-opener", refsFor(reqForTarget).focusId);
        cancelButton.click();
        switcher.switchForm();
    });

    cancelButton.addEventListener("click", (e) => {
        if(e.isTrusted){
                const switcher = getSwitcher()
                if(switcher.isRecordType){
                    switcher.updateSelectedType(switcher.pending.recordId);
                }
                switcher && switcher.resetPendingAndTarget()
           }
        }
    );


    // addRecordButtonEventListener(alpineData, initialState, container)
    const addRecordButton = document.getElementById("add-dnsrecord-button")?.addEventListener("click", ()=> {
        editFormSwitcher.attemptOpen(0);
        onCancel(editFormSwitcher);
    })
    // add edit button event listener
    editButtonEventListener(editFormSwitcher)

    // add switch form type event listener
    const recordTypeSwitcher = new RecordSelectTypeSwitcher(selector);
    const selectRecordType = selector?.addEventListener("change", (e)=> {
        if(!e.isTrusted){
            return;
        }
        const index = e.target.selectedIndex;
        recordTypeSwitcher.attemptOpen(index);
        onCancel(recordTypeSwitcher)
    })
    
}

// Tab-order routing for the DNS records table (#4804).
// When a form is open, route Tab to walk:
//   Edit → form fields → Form Delete → Row Delete → next row's Edit
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
        const rowDelete = table.querySelector(
            `button[id="row-delete-button-${recordId}"]`
        );
        if (!editBtn || !formRow) return null;
        const formFirst = formRow.querySelector(
            'input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled])'
        );
        const formDelete = formRow.querySelector('[data-action="form-delete"]');
        return { editBtn, formRow, rowDelete, formFirst, formDelete };
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
            if (past && el.offsetParent !== null){
                if (!table.contains(el)) return el;
            }
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
        const recordId = getOpenRecordId();
        const nextRecordEntry = recordId ? nextRecordEntryAfter(recordId) : null;
        // Tab/Shift+Tab from any record's Edit button: route based on that record's
        // form state, regardless of whether any other form is open.
        const editBtn = t.closest?.('[data-action="edit"]');
        if (editBtn === t && editBtn !== nextRecordEntry) {
            const recordId = editBtn.dataset.recordId;
            const r = getRecordElements(recordId);
            if (!r) return;
            const isOpen = getOpenRecordId() === recordId;
            if (!e.shiftKey) {
                // Edit -> first form field (open) | rowDelete
                e.preventDefault();
                (isOpen ? r.formFirst : r.rowDelete)?.focus();
            }
            // Shift+Tab from Edit: let natural DOM order go to the previous focusable.
            return;
        }

        // The remaining rules apply only while a form is open.
        if (!recordId) return;
        const elems = getRecordElements(recordId);
        if (!elems) return;

        const isRowDeleteFocus = elems.rowDelete && (t === elems.rowDelete);

        // First form field -> Edit (Shift+Tab backward)
        if (e.shiftKey && t === elems.formFirst) {
            e.preventDefault();
            elems.editBtn.focus();
            return;
        }
        // Form Delete -> row delete (Tab forward)
        if (!e.shiftKey && elems.formDelete && t === elems.formDelete) {
            e.preventDefault();
            elems.rowDelete?.focus();
            return;
        }
        // Row delete -> Form Delete (Shift+Tab backward, form open)
        if (e.shiftKey && isRowDeleteFocus) {
            e.preventDefault();
            elems.formDelete?.focus();
            return;
        }
        // Next record's Edit -> Row delete (Shift+Tab backward, form open)
        if (e.shiftKey && elems.rowDelete && t === nextRecordEntry) {
            e.preventDefault();
            elems.rowDelete.focus();
            return;
        }
        // Row delete -> next record's Edit / out of table (Tab forward, form open — skip the
        // visible form row that would otherwise be next in DOM order).
        if (!e.shiftKey && isRowDeleteFocus) {
            const destination = nextRecordEntry || nextFocusableAfterElement(table);
            if (!destination) return;
            e.preventDefault();
            destination.focus();
            return;
        }
    });
}

// Issue #4629: after a DNS record submit, move focus to the first alert in
// #messages-container once htmx finishes swapping it in. Alerts carry
// tabindex="-1" in form_messages.html so they're focusable but not tabbable.
export function initDNSRecordAlertFocus() {
    const dnsRecordsContainer = document.getElementById("dnsrecords-form-container");
    if (!dnsRecordsContainer) return;

    document.body.addEventListener("htmx:afterSettle", (evt) => {
        const swapped = evt?.detail?.target || evt?.target;
        if (swapped?.id !== "messages-container") return;

        const firstAlert = swapped.querySelector(".usa-alert");
        if (firstAlert) firstAlert.focus();
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
}

export function initDeleteDnsRecord() {
    const table = document.getElementById("dnsrecords-table");

    table?.addEventListener("click", (e) => {
        const deleteBtn = e.target.closest(".js-dnsrecord-delete");
        if(!deleteBtn) return;

        const recordId = deleteBtn.dataset.recordId
        e.preventDefault()

        const focusElement = deleteBtn;
        const modal = document.getElementById("delete-dns-record-modal");
        const modalTrigger = document.getElementById("delete-dns-record-modal-trigger")
        openModal(modalTrigger, modal, focusElement);
    });

    const openModal = (modalTrigger, modal, focusElement) => {
            // Listen for when the modal closes
        if (modal) {
            const closeButtons = modal.querySelectorAll("[data-close-modal]")

            // targets the "X" and "Cancel" or "Go back" and moves focus to the focusElement after closing the modal
            closeButtons.forEach(btn => {
                btn.addEventListener("click", () => {
                    // Defer focus restoration to after modal closes
                    focusElement?.focus()
                    setTimeout(() => {
                        focusElement?.focus();
                    }, 50);
                }, { once: true });
            });

            // Handle ESC key press to close modal --> move focus to focusElement
            const handleEscKey = (e) => {
                if (e.key === "Escape") {
                    setTimeout(() => {
                        focusElement?.focus();
                    }, 50);
                    document.removeEventListener("keydown", handleEscKey);
                }
            };

            document.addEventListener("keydown", handleEscKey);
        }
        modalTrigger?.click()
    }
}
