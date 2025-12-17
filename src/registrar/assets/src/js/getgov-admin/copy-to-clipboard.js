
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

// This method copies an individual email to the clipboard from the admins/members table in portfolio
function copyIndividualTextButtonToClipBoard(button) {
    // Assuming the input is the previous sibling of the button
    let input = button.previousElementSibling;
    // Copy input value to clipboard
    if (input && input instanceof HTMLInputElement) {
       const buttonSelector = ".copy-to-clipboard"
       copyToClipboardAndChangeIcon(button, input.value, buttonSelector)
    }
}

// method checks if emails are captured, and calls the method to capture to clipboard
function copyAllMembersAdminsToClipboard(button, table_id, button_id){
    const membersEmails = helperCopyEmailsFromTableFunction(table_id);
    if(membersEmails){
        copyToClipboardAndChangeIcon(button, membersEmails, button_id)
    }

}

// method that captures the content(email) into a comma seperated list
function helperCopyEmailsFromTableFunction(table){
    const myTable = document.querySelector(table); 
    const emailCells = myTable.querySelectorAll('[data-column-id="email"]')
    let emails= []
    for(let i = 0; i < emailCells.length; i++){
        const email = emailCells[i].textContent.trim()
        if(email != "None") {
            emails.push(email)
        }
    }
    return emails.join(",")
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

    const portfolioMemberSelectorId = "#copy-to-clipboard-members"
    const portfolioMembersButton = document.querySelector(portfolioMemberSelectorId)
    portfolioMembersButton && portfolioMembersButton.addEventListener("click", ()=>{
        copyAllMembersAdminsToClipboard(portfolioMembersButton, "#portfolio-members-table", portfolioMemberSelectorId)
    })

    const portfolioAdminsSelectorId = "#copy-to-clipboard-admins"
    const portfolioAdminsButton = document.querySelector(portfolioAdminsSelectorId)
    portfolioAdminsButton && portfolioAdminsButton.addEventListener("click", ()=>{
        copyAllMembersAdminsToClipboard(portfolioAdminsButton, "#portfolio-admins-table", portfolioAdminsSelectorId)
     }
    )
}
