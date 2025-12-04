
// This function takes data and copies it to the user's clipboard
// it also changes the icon from "copy" to "copied to clipboard" when a user clicks 
function copyToClipboardAndChangeIcon(button, input, selector) {
        navigator.clipboard.writeText(input).then(function() {
            // Change the icon to a checkmark on successful copy
            let buttonIcon = button.querySelector(selector + " use");
            
            if (buttonIcon) {
                let currentHref = buttonIcon.getAttribute('xlink:href');
                let baseHref = currentHref.split('#')[0];

                // Append the new icon reference
                buttonIcon.setAttribute('xlink:href', baseHref + '#check');

                // Change the button text
                let nearestSpan = button.querySelector("span")
                let original_text = nearestSpan.innerText
                nearestSpan.innerText = "Copied to clipboard"

                setTimeout(function() {
                    // Change back to the copy icon
                    buttonIcon.setAttribute('xlink:href', currentHref); 
                    nearestSpan.innerText = original_text;
                }, 2000);

            }
        }).catch(function(error) {
            console.error('Clipboard copy failed', error);
        });
}

function copyIndividualTextButtonToClipBoard(button) {
    // Assuming the input is the previous sibling of the button
    let input = button.previousElementSibling;
    // Copy input value to clipboard
    if (input) {
       const buttonSelector = ".copy-to-clipboard"
       copyToClipboardAndChangeIcon(button, input.value, buttonSelector)
    }
}

function copyAllMembersAdminsToClipboard(button, table, buttonSelector){
    const membersInCsv = helperCopyMembersTableFunction(table);
    if(membersInCsv){
        copyToClipboardAndChangeIcon(button, membersInCsv, buttonSelector)
    }

}

function helperCopyMembersTableFunction(table){
    const myTable = document.querySelector(table); 
    let copyOfTableToCsv = ""
   
    const rows = myTable.querySelectorAll('tr')
    
    //header rows
    // Minus 2 on the iterator, the last column has copy icons
    const headerRow = rows[0].querySelectorAll('th')
    for(let i = 0; i <= headerRow.length - 2; i++){
        let headerText = headerRow[i].textContent.trim()
        copyOfTableToCsv+= headerText + ","

        // add new line to the csv header row
        if(i == headerRow.length - 2){
            copyOfTableToCsv += "\n"
        }
    }

    //body rows
    for(let i = 1; i < rows.length; i++){
       let rowText = ""
        const bodyRows = rows[i].querySelectorAll('td');
        for(let j = 0; j < bodyRows.length - 1; j++){
            rowText+= bodyRows[j].textContent.trim() + ","
        }
        copyOfTableToCsv+= rowText + "\n"
    }

    return copyOfTableToCsv
}

/**
 * A function for pages in DjangoAdmin that use a clipboard button
*/
export function initCopyToClipboard() {
    let clipboardButtons = document.querySelectorAll(".copy-to-clipboard")
    clipboardButtons.forEach((button) => {

        // Handle copying the text to your clipboard,
        // and changing the icon.
        button.addEventListener("click", ()=>{
            copyIndividualTextButtonToClipBoard(button);
        });
        
        // Add a class that adds the outline style on click
        button.addEventListener("mousedown", function() {
            this.classList.add("no-outline-on-click");
        });
        
        // But add it back in after the user clicked,
        // for accessibility reasons (so we can still tab, etc)
        button.addEventListener("blur", function() {
            this.classList.remove("no-outline-on-click");
        });

    });

    const portfolioMemberSelectorButton = "#copy-to-clipboard-members"
    const portfolioMembersButton = document.querySelector(portfolioMemberSelectorButton)
    portfolioMembersButton && portfolioMembersButton.addEventListener("click", ()=>{
        copyAllMembersAdminsToClipboard(portfolioMembersButton, "#portfolio-members-table", portfolioMemberSelectorButton)
    })

    const portfolioAdminsSelectorButton = "#copy-to-clipboard-admins"
    const portfolioAdminsButton = document.querySelector(portfolioAdminsSelectorButton)
    portfolioAdminsButton && portfolioAdminsButton.addEventListener("click", ()=>{
        copyAllMembersAdminsToClipboard(portfolioAdminsButton, "#portfolio-admins-table", portfolioAdminsSelectorButton )
     }
    )
}

