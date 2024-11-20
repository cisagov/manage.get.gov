export function userProfileListener() {
  const showConfirmationModalTrigger = document.querySelector('.show-confirmation-modal');
  if (showConfirmationModalTrigger) {
    showConfirmationModalTrigger.click();
  }
}

export function finishUserSetupListener() {
  
  function getInputField(fieldName){
    return document.querySelector(`#id_${fieldName}`)
  }

  // Shows the hidden input field and hides the readonly one
  function showInputFieldHideReadonlyField(fieldName, button) {
    let inputField = getInputField(fieldName)
    let readonlyField = document.querySelector(`#${fieldName}__edit-button-readonly`)

    readonlyField.classList.toggle('display-none');
    inputField.classList.toggle('display-none');

    // Toggle the bold style on the grid row
    let gridRow = button.closest(".grid-col-2").closest(".grid-row")
    if (gridRow){
      gridRow.classList.toggle("bold-usa-label")
    }
  }

  function handleFullNameField(fieldName = "full_name") {
    // Remove the display-none class from the nearest parent div
    let nameFieldset = document.querySelector("#profile-name-group");
    if (nameFieldset){
      nameFieldset.classList.remove("display-none");
    }

    // Hide the "full_name" field
    let inputField = getInputField(fieldName);
    if (inputField) {
      let inputFieldParentDiv = inputField.closest("div");
      if (inputFieldParentDiv) {
        inputFieldParentDiv.classList.add("display-none");
      }
    }
  }

  function handleEditButtonClick(fieldName, button){
    button.addEventListener('click', function() {
      // Lock the edit button while this operation occurs
      button.disabled = true

      if (fieldName == "full_name"){
        handleFullNameField();
      }else {
        showInputFieldHideReadonlyField(fieldName, button);
      }
      
      // Hide the button itself
      button.classList.add("display-none");

      // Unlock after it completes
      button.disabled = false
    });
  }

  function setupListener(){
    document.querySelectorAll('[id$="__edit-button"]').forEach(function(button) {
      // Get the "{field_name}" and "edit-button"
      let fieldIdParts = button.id.split("__")
      if (fieldIdParts && fieldIdParts.length > 0){
        let fieldName = fieldIdParts[0]
        
        // When the edit button is clicked, show the input field under it
        handleEditButtonClick(fieldName, button);

        let editableFormGroup = button.parentElement.parentElement.parentElement;
        if (editableFormGroup){
          let readonlyField = editableFormGroup.querySelector(".toggleable_input__readonly-field")
          let inputField = document.getElementById(`id_${fieldName}`);
          if (!inputField || !readonlyField) {
            return;
          }

          let inputFieldValue = inputField.value
          if (inputFieldValue || fieldName == "full_name"){
            if (fieldName == "full_name"){
              let firstName = document.querySelector("#id_first_name");
              let middleName = document.querySelector("#id_middle_name");
              let lastName = document.querySelector("#id_last_name");
              if (firstName && lastName && firstName.value && lastName.value) {
                let values = [firstName.value, middleName.value, lastName.value]
                readonlyField.innerHTML = values.join(" ");
              }else {
                let fullNameField = document.querySelector('#full_name__edit-button-readonly');
                let svg = fullNameField.querySelector("svg use")
                if (svg) {
                  const currentHref = svg.getAttribute('xlink:href');
                  if (currentHref) {
                    const parts = currentHref.split('#');
                    if (parts.length === 2) {
                      // Keep the path before '#' and replace the part after '#' with 'invalid'
                      const newHref = parts[0] + '#error';
                      svg.setAttribute('xlink:href', newHref);
                      fullNameField.classList.add("toggleable_input__error")
                      label = fullNameField.querySelector(".toggleable_input__readonly-field")
                      label.innerHTML = "Unknown";
                    }
                  }
                }
              }
              
              // Technically, the full_name field is optional, but we want to display it as required. 
              // This style is applied to readonly fields (gray text). This just removes it, as
              // this is difficult to achieve otherwise by modifying the .readonly property.
              if (readonlyField.classList.contains("text-base")) {
                readonlyField.classList.remove("text-base")
              }
            }else {
              readonlyField.innerHTML = inputFieldValue
            }
          }
        }
      }
    });
  }

  function showInputOnErrorFields(){
    document.addEventListener('DOMContentLoaded', function() {

      // Get all input elements within the form
      let form = document.querySelector("#finish-profile-setup-form");
      let inputs = form ? form.querySelectorAll("input") : null;
      if (!inputs) {
        return null;
      }

      let fullNameButtonClicked = false
      inputs.forEach(function(input) {
        let fieldName = input.name;
        let errorMessage = document.querySelector(`#id_${fieldName}__error-message`);

        // If no error message is found, do nothing
        if (!fieldName || !errorMessage) {
          return null;
        }

        let editButton = document.querySelector(`#${fieldName}__edit-button`);
        if (editButton){
          // Show the input field of the field that errored out 
          editButton.click();
        }

        // If either the full_name field errors out,
        // or if any of its associated fields do - show all name related fields.
        let nameFields = ["first_name", "middle_name", "last_name"];
        if (nameFields.includes(fieldName) && !fullNameButtonClicked){
          // Click the full name button if any of its related fields error out
          fullNameButton = document.querySelector("#full_name__edit-button");
          if (fullNameButton) {
            fullNameButton.click();
            fullNameButtonClicked = true;
          }
        }
      });  
    });
  };

  setupListener();

  // Show the input fields if an error exists
  showInputOnErrorFields();
}
