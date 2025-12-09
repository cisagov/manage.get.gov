
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
    if (input) {
       const buttonSelector = ".copy-to-clipboard"
       copyToClipboardAndChangeIcon(button, input.value, buttonSelector)
    }
}

// method checks if emails are captured, and calls the method to capture to clipboard
function copyAllMembersAdminsToClipboard(button, table, buttonSelector){
    const membersEmails = helperCopyEmailsFromTableFunction(table);
    if(membersEmails){
        copyToClipboardAndChangeIcon(button, membersEmails, buttonSelector)
    }

}

// method that captures the content(email) into a comma seperated list
function helperCopyEmailsFromTableFunction(table){
    const myTable = document.querySelector(table); 
    let emails= ""
   
    const rows = myTable.querySelectorAll('tr')

    //body rows
    // started at second row for content
    for(let i = 1; i < rows.length; i++){
        const bodyRows = rows[i].querySelectorAll('td')
        // email is the third item from the end of the row
        const emailI = bodyRows.length - 3 
        const emailText = bodyRows[emailI].textContent.trim()
        emails+= emailText + ","
    }

    return emails
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

