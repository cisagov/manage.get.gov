function copyToClipboardAndChangeIcon(button) {
    // Assuming the input is the previous sibling of the button
    let input = button.previousElementSibling;
    // Copy input value to clipboard
    if (input) {
        navigator.clipboard.writeText(input.value).then(function() {
            // Change the icon to a checkmark on successful copy
            let buttonIcon = button.querySelector('.copy-to-clipboard use');
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
            copyToClipboardAndChangeIcon(button);
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
}
