/**
 * A function for pages in DjangoAdmin that use modals.
 * Dja strips out form elements, and modals generate their content outside
 * of the current form scope, so we need to "inject" these inputs.
*/
export function initModals(){
    let submitButtons = document.querySelectorAll('.usa-modal button[type="submit"].dja-form-placeholder');
    let form = document.querySelector("form")
    submitButtons.forEach((button) => {

        let input = document.createElement("input");
        input.type = "submit";

        if(button.name){
            input.name = button.name;
        }

        if(button.value){
            input.value = button.value;
        }

        input.style.display = "none"

        // Add the hidden input to the form
        form.appendChild(input);
        button.addEventListener("click", () => {
            input.click();
        })
    })
}
