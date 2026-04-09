// Establishes javascript for dynamic content label based on type

// Observer setup, persist across HTMX updates
let characterCountObserverSetup = false;

function setupCharacterCountObservers() {
  if (characterCountObserverSetup) return;

  characterCountObserverSetup = true;

  // Observer to handle new character count elements added to existing containers
  const containerObserver = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.addedNodes.length) {
        mutation.addedNodes.forEach((node) => {
          if (node.classList && node.classList.contains('usa-character-count__status')) {
            updateCharacterCountMessage(node);
          }
        });
      }
    });
  });

  // Observer to handle new character count containers being added to the DOM
  const newContainerObserver = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.addedNodes.length) {
        mutation.addedNodes.forEach((node) => {
          if (node.classList && node.classList.contains('usa-character-count')) {
            // Update any status messages in the new container
            node.querySelectorAll('.usa-character-count__status').forEach((el) => {
              updateCharacterCountMessage(el);
            });
            // Observe this new container for future updates
            containerObserver.observe(node, {
              childList: true,
            });
          }
        });
      }
    });
  });

  // Watch for new character count containers being added
  newContainerObserver.observe(document.body, {
    childList: true,
    subtree: true,
  });

  // Observe existing character count containers
  document.querySelectorAll('.usa-character-count').forEach((container) => {
    containerObserver.observe(container, {
      childList: true,
    });
  });
}

// Override USWDS character count messages to use "characters left" instead of 
// "characters allowed" and handle singular/plural
function overrideUSWDSCharacterCount() {
  // Setup observers to handle dynamic content changes and ensure character 
  // count messages are accurate and updated
  setupCharacterCountObservers();

  // Create missing character count status elements and attach listeners
  document.querySelectorAll('.usa-character-count').forEach((container) => {
    const field = container.querySelector('.usa-character-count__field');
    if (!field) return;

    const statusEl = container.querySelector('.usa-character-count__status');
    if (!statusEl) {
      const maxLength = field.getAttribute('maxlength') || container.getAttribute('data-maxlength');
      const charactersLeft = maxLength - (field.value ? field.value.length : 0);

      let message;
      if (charactersLeft >= 0) {
        const characters = `character${charactersLeft === 1 ? '' : 's'}`;
        message = `${charactersLeft} ${characters} left`;
      } else {
        const absCount = Math.abs(charactersLeft);
        const characters = `character${absCount === 1 ? '' : 's'}`;
        message = `${absCount} ${characters} over limit`;
      }

      const newStatus = document.createElement('div');
      newStatus.className = 'usa-character-count__status usa-hint';
      newStatus.setAttribute('aria-hidden', 'true');
      newStatus.textContent = message;

      // Insert after the message span
      const messageSpan = container.querySelector('.usa-character-count__message');
      if (messageSpan) {
        messageSpan.insertAdjacentElement('afterend', newStatus);
      } else {
        container.appendChild(newStatus);
      }
    }

    // Attach input listener to update character count as user types
    if (!field.dataset.characterCountListenerAttached) {
      field.addEventListener('input', function () {
        const maxLength = this.getAttribute('maxlength') || container.getAttribute('data-maxlength');
        const charactersLeft = maxLength - this.value.length;
        const status = container.querySelector('.usa-character-count__status');
        if (status) {
          if (charactersLeft >= 0) {
            const characters = `character${charactersLeft === 1 ? '' : 's'}`;
            status.textContent = `${charactersLeft} ${characters} left`;
          } else {
            const absCount = Math.abs(charactersLeft);
            const characters = `character${absCount === 1 ? '' : 's'}`;
            status.textContent = `${absCount} ${characters} over limit`;
          }
          status.classList.toggle('usa-character-count__status--invalid', this.value.length > maxLength);
        }
      });
      field.dataset.characterCountListenerAttached = 'true';
    }
  });

  // Update any existing character count messages (this runs every time) 
  // to ensure they reflect the correct counts and use the new message format
  document.querySelectorAll('.usa-character-count__status').forEach((el) => {
    updateCharacterCountMessage(el);
  });
}

function updateCharacterCountMessage(element) {
  // Find the associated field and recalculate based on actual content
  const container = element.closest('.usa-character-count');
  if (!container) return;

  const field = container.querySelector('.usa-character-count__field');
  if (!field) return;

  const maxLength = field.getAttribute('maxlength') || container.getAttribute('data-maxlength');
  const charactersLeft = maxLength - (field.value ? field.value.length : 0);

  if (charactersLeft >= 0) {
    const characters = `character${charactersLeft === 1 ? '' : 's'}`;
    element.textContent = `${charactersLeft} ${characters} left`;
  } else {
    const absCount = Math.abs(charactersLeft);
    const characters = `character${absCount === 1 ? '' : 's'}`;
    element.textContent = `${absCount} ${characters} over limit`;
  }
}

function createCharacterCountText(charLimit, textArea) {
  let getCharCountText = function () {
    const charactersLeft = charLimit - textArea.value.length;
    if (charactersLeft >= 0) {
      const characters = `character${charactersLeft === 1 ? '' : 's'}`;
      return `${charactersLeft} ${characters} left`;
    } else {
      const characters = `character${Math.abs(charactersLeft) === 1 ? '' : 's'}`;
      return `${Math.abs(charactersLeft)} ${characters} over limit`;
    }
  };
  const displayCharCount = document.createElement('div');
  displayCharCount.className = 'usa-character-count__status usa-hint';
  displayCharCount.textContent = getCharCountText();
  textArea.addEventListener('input', function () {
    displayCharCount.textContent = getCharCountText();
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
        const displayCharCount = createCharacterCountText(charLimit, textArea)

        element.replaceWith(textArea)
        textArea.insertAdjacentElement('afterend', displayCharCount)
}



export function initCharacterCountOverrides() {
  overrideUSWDSCharacterCount();
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

            if(commenttBtn){
                if(alpineData.showFormId === recordId) alpineData.showFormId = null;
                const idx = alpineData.openComments.indexOf(recordId);
                idx > -1 ? alpineData.openComments.splice(idx,1) : alpineData.openComments.push(recordId)

            }
        
        })
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