
function addForm(e, nameServerRows){
    let formspace = document.getElementsByClassName("nameservers-form");

    function formTemplate(num) {
        return (
            `<fieldset class="usa-fieldset"> 
            <label class="usa-label" for="given-name">Name server ${num} </label>
            <div class="usa-hint" id="gnHint">Example: ns${num}.example.com</div>
            <input
              class="usa-input usa-input--xl"
              id="given-name"
              name="first-name"
              aria-describedby="gnHint"
            />
        </form>`
        )
    }

     
    if(nameServerRows.length > 0){
        for(let i = 0; i < 1; i++){
            formspace.add(formTemplate(i + 1))
        }
    }
    else{
        formspace.add(formTemplate(nameServerRows.length + 1))
    }  
}

export function domainNameServers() {
    let addButton = document.querySelector("#nameserver-add-form");
    let nameServerRows = document.querySelectorAll("nameserver-row");
    addButton.addEventListener('click', addForm(nameServerRows));
   
}

// need a listener for save and cancel to hide the form when clicked
// add function to add rows to the table after submiting form