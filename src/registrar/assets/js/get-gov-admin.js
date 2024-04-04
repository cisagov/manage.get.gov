/**
 * @file get-gov-admin.js includes custom code for the .gov registrar admin portal.
 *
 * Constants and helper functions are at the top.
 * Event handlers are in the middle.
 * Initialization (run-on-load) stuff goes at the bottom.
 */

// <<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>>
// Helper functions.
/** Either sets attribute target="_blank" to a given element, or removes it */
function openInNewTab(el, removeAttribute = false){
    if(removeAttribute){
        el.setAttribute("target", "_blank");
    }else{
        el.removeAttribute("target", "_blank");
    }
};

// <<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>>
// Event handlers.

// <<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>><<>>
// Initialization code.

/** An IIFE for pages in DjangoAdmin that use modals.
 * Dja strips out form elements, and modals generate their content outside
 * of the current form scope, so we need to "inject" these inputs.
*/
(function (){
    function createPhantomModalFormButtons(){
        let submitButtons = document.querySelectorAll('.usa-modal button[type="submit"].dja-form-placeholder');
        form = document.querySelector("form")
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

    createPhantomModalFormButtons();
})();

/** An IIFE for DomainRequest to hook a modal to a dropdown option.
 * This intentionally does not interact with createPhantomModalFormButtons()
*/
(function (){
    function displayModalOnDropdownClick(linkClickedDisplaysModal, statusDropdown, actionButton, valueToCheck){

        // If these exist all at the same time, we're on the right page
        if (linkClickedDisplaysModal && statusDropdown && statusDropdown.value){
            
            // Set the previous value in the event the user cancels.
            let previousValue = statusDropdown.value;
            if (actionButton){

                // Otherwise, if the confirmation buttion is pressed, set it to that
                actionButton.addEventListener('click', function() {
                    // Revert the dropdown to its previous value
                    statusDropdown.value = valueToCheck;
                });
            }else {
                console.log("displayModalOnDropdownClick() -> Cancel button was null")
            }

            // Add a change event listener to the dropdown.
            statusDropdown.addEventListener('change', function() {
                // Check if "Ineligible" is selected
                if (this.value && this.value.toLowerCase() === valueToCheck) {
                    // Set the old value in the event the user cancels,
                    // or otherwise exists the dropdown.
                    statusDropdown.value = previousValue

                    // Display the modal.
                    linkClickedDisplaysModal.click()
                }
            });
        }
    }

    // When the status dropdown is clicked and is set to "ineligible", toggle a confirmation dropdown.
    function hookModalToIneligibleStatus(){
        // Grab the invisible element that will hook to the modal.
        // This doesn't technically need to be done with one, but this is simpler to manage.
        let modalButton = document.getElementById("invisible-ineligible-modal-toggler")
        let statusDropdown = document.getElementById("id_status")

        // Because the modal button does not have the class "dja-form-placeholder",
        // it will not be affected by the createPhantomModalFormButtons() function.
        let actionButton = document.querySelector('button[name="_set_domain_request_ineligible"]');
        let valueToCheck = "ineligible"
        displayModalOnDropdownClick(modalButton, statusDropdown, actionButton, valueToCheck);
    }

    hookModalToIneligibleStatus()
})();

/** An IIFE for pages in DjangoAdmin which may need custom JS implementation.
 * Currently only appends target="_blank" to the domain_form object,
 * but this can be expanded.
*/
(function (){
    /*
    On mouseover, appends target="_blank" on domain_form under the Domain page.
    The reason for this is that the template has a form that contains multiple buttons.
    The structure of that template complicates seperating those buttons 
    out of the form (while maintaining the same position on the page).
    However, if we want to open one of those submit actions to a new tab - 
    such as the manage domain button - we need to dynamically append target.
    As there is no built-in django method which handles this, we do it here. 
    */
    function prepareDjangoAdmin() {
        let domainFormElement = document.getElementById("domain_form");
        let domainSubmitButton = document.getElementById("manageDomainSubmitButton");
        if(domainSubmitButton && domainFormElement){
            domainSubmitButton.addEventListener("mouseover", () => openInNewTab(domainFormElement, true));
            domainSubmitButton.addEventListener("mouseout", () => openInNewTab(domainFormElement, false));
        }
    }

    prepareDjangoAdmin();
})();

/** An IIFE for pages in DjangoAdmin that use a clipboard button
*/
(function (){

    function copyInnerTextToClipboard(elem) {
        let text = elem.innerText
        navigator.clipboard.writeText(text)
    }

    function copyToClipboardAndChangeIcon(button) {
        // Assuming the input is the previous sibling of the button
        let input = button.previousElementSibling;
        let userId = input.getAttribute("user-id")
        // Copy input value to clipboard
        if (input) {
            navigator.clipboard.writeText(input.value).then(function() {
                // Change the icon to a checkmark on successful copy
                let buttonIcon = button.querySelector('.usa-button__clipboard use');
                if (buttonIcon) {
                    let currentHref = buttonIcon.getAttribute('xlink:href');
                    let baseHref = currentHref.split('#')[0];

                    // Append the new icon reference
                    buttonIcon.setAttribute('xlink:href', baseHref + '#check');

                    // Find the nearest .admin-icon-group__success-dialog and update its classes
                    let brElement = null
                    let successDialog = document.querySelector(`#email-clipboard__success-dialog-${userId}`);
                    if (successDialog) {
                        successDialog.classList.remove('display-none');
                        // Find the associated BR if it exists
                        brElement = successDialog.nextElementSibling
                    }
                    
                    // If the element directly below the success dialog is a br, hide it.
                    // This is for dynamic styling reasons
                    if (brElement && brElement.tagName === 'BR' && brElement.classList.contains('admin-icon-group__br')) {
                        brElement.classList.add('display-none');
                    }

                    setTimeout(function() {
                        // Change back to the copy icon
                        buttonIcon.setAttribute('xlink:href', currentHref); 

                        // Hide the success dialog
                        if (successDialog){
                            successDialog.classList.add("display-none");
                        }
                        
                        // Show the regular br
                        if (brElement) {
                            brElement.classList.remove("display-none");
                        }
                    }, 1500);

                }

            }).catch(function(error) {
                console.error('Clipboard copy failed', error);
            });
        }
    }
    
    function handleClipboardButtons() {
        clipboardButtons = document.querySelectorAll(".usa-button__clipboard")
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

    function handleClipboardLinks() {
        let emailButtons = document.querySelectorAll(".usa-button__clipboard-link");
        if (emailButtons){
            emailButtons.forEach((button) => {
                button.addEventListener("click", ()=>{
                    copyInnerTextToClipboard(button);
                })
            });
        }
    }

    handleClipboardButtons();
    handleClipboardLinks();

})();


/**
 * An IIFE to listen to changes on filter_horizontal and enable or disable the change/delete/view buttons as applicable
 *
 */
(function extendFilterHorizontalWidgets() {
    // Initialize custom filter_horizontal widgets; each widget has a "from" select list
    // and a "to" select list; initialization is based off of the presence of the
    // "to" select list
    checkToListThenInitWidget('id_other_contacts_to', 0);
    checkToListThenInitWidget('id_domain_info-0-other_contacts_to', 0);
    checkToListThenInitWidget('id_current_websites_to', 0);
    checkToListThenInitWidget('id_alternative_domains_to', 0);
})();

// Function to check for the existence of the "to" select list element in the DOM, and if and when found,
// initialize the associated widget
function checkToListThenInitWidget(toListId, attempts) {
    let toList = document.getElementById(toListId);
    attempts++;

    if (attempts < 6) {
        if ((toList !== null)) {
            // toList found, handle it
            // Add an event listener on the element
            // Add disabled buttons on the element's great-grandparent
            initializeWidgetOnToList(toList, toListId);
        } else {
            // Element not found, check again after a delay
            setTimeout(() => checkToListThenInitWidget(toListId, attempts), 1000); // Check every 1000 milliseconds (1 second)
        }
    }
}

// Initialize the widget:
//  add related buttons to the widget for edit, delete and view
//  add event listeners on the from list, the to list, and selector buttons which either enable or disable the related buttons
function initializeWidgetOnToList(toList, toListId) {
    // create the change button
    let changeLink = createAndCustomizeLink(
        toList,
        toListId,
        'related-widget-wrapper-link change-related',
        'Change',
        '/public/admin/img/icon-changelink.svg',
        {
            'contacts': '/admin/registrar/contact/__fk__/change/?_to_field=id&_popup=1',
            'websites': '/admin/registrar/website/__fk__/change/?_to_field=id&_popup=1',
            'alternative_domains': '/admin/registrar/website/__fk__/change/?_to_field=id&_popup=1',
        },
        true,
        true
    );

    let hasDeletePermission = hasDeletePermissionOnPage();

    let deleteLink = null;
    if (hasDeletePermission) {
        // create the delete button if user has permission to delete
        deleteLink = createAndCustomizeLink(
            toList,
            toListId,
            'related-widget-wrapper-link delete-related',
            'Delete',
            '/public/admin/img/icon-deletelink.svg',
            {
                'contacts': '/admin/registrar/contact/__fk__/delete/?_to_field=id&amp;_popup=1',
                'websites': '/admin/registrar/website/__fk__/delete/?_to_field=id&_popup=1',
                'alternative_domains': '/admin/registrar/website/__fk__/delete/?_to_field=id&_popup=1',
            },
            true,
            false
        );
    }

    // create the view button
    let viewLink = createAndCustomizeLink(
        toList,
        toListId,
        'related-widget-wrapper-link view-related',
        'View',
        '/public/admin/img/icon-viewlink.svg',
        {
            'contacts': '/admin/registrar/contact/__fk__/change/?_to_field=id',
            'websites': '/admin/registrar/website/__fk__/change/?_to_field=id',
            'alternative_domains': '/admin/registrar/website/__fk__/change/?_to_field=id',
        },
        // NOTE: If we open view in the same window then use the back button
        // to go back, the 'chosen' list will fail to initialize correctly in
        // sandbozes (but will work fine on local). This is related to how the
        // Django JS runs (SelectBox.js) and is probably due to a race condition.
        true,
        false
    );

    // identify the fromList element in the DOM
    let fromList = toList.closest('.selector').querySelector(".selector-available select");

    fromList.addEventListener('click', function(event) {
        handleSelectClick(fromList, changeLink, deleteLink, viewLink);
    });
    
    toList.addEventListener('click', function(event) {
        handleSelectClick(toList, changeLink, deleteLink, viewLink);
    });
    
    // Disable buttons when the selectors are interacted with (items are moved from one column to the other)
    let selectorButtons = [];
    selectorButtons.push(toList.closest(".selector").querySelector(".selector-chooseall"));
    selectorButtons.push(toList.closest(".selector").querySelector(".selector-add"));
    selectorButtons.push(toList.closest(".selector").querySelector(".selector-remove"));

    selectorButtons.forEach((selector) => {
        selector.addEventListener("click", ()=>{disableRelatedWidgetButtons(changeLink, deleteLink, viewLink)});
      });
}

// create and customize the button, then add to the DOM, relative to the toList
//  toList - the element in the DOM for the toList
//  toListId - the ID of the element in the DOM
//  className - className to add to the created link
//  action - the action to perform on the item {change, delete, view}
//  imgSrc - the img.src for the created link
//  dataMappings - dictionary which relates toListId to href for the created link
//  dataPopup - boolean for whether the link should produce a popup window
//  firstPosition - boolean indicating if link should be first position in list of links, otherwise, should be last link
function createAndCustomizeLink(toList, toListId, className, action, imgSrc, dataMappings, dataPopup, firstPosition) {
    // Create a link element
    var link = document.createElement('a');

    // Set class attribute for the link
    link.className = className;

    // Set id
    // Determine function {change, link, view} from the className
    // Add {function}_ to the beginning of the string
    let modifiedLinkString = className.split('-')[0] + '_' + toListId;
    // Remove '_to' from the end of the string
    modifiedLinkString = modifiedLinkString.replace('_to', '');
    link.id = modifiedLinkString;

    // Set data-href-template
    for (const [idPattern, template] of Object.entries(dataMappings)) {
        if (toListId.includes(idPattern)) {
            link.setAttribute('data-href-template', template);
            break; // Stop checking once a match is found
        }
    }

    if (dataPopup)
        link.setAttribute('data-popup', 'yes');
    
    link.setAttribute('title-template', action + " selected item")
    link.title = link.getAttribute('title-template');

    // Create an 'img' element
    var img = document.createElement('img');

    // Set attributes for the new image
    img.src = imgSrc;
    img.alt = action;

    // Append the image to the link
    link.appendChild(img);

    let relatedWidgetWrapper = toList.closest('.related-widget-wrapper');
    // If firstPosition is true, insert link as the first child element
    if (firstPosition) {
        relatedWidgetWrapper.insertBefore(link, relatedWidgetWrapper.children[0]);
    } else {
        // otherwise, insert the link prior to the last child (which is a div)
        // and also prior to any text elements immediately preceding the last
        // child node
        var lastChild = relatedWidgetWrapper.lastChild;

        // Check if lastChild is an element node (not a text node, comment, etc.)
        if (lastChild.nodeType === 1) {
            var previousSibling = lastChild.previousSibling;
            // need to work around some white space which has been inserted into the dom
            while (previousSibling.nodeType !== 1) {
                previousSibling = previousSibling.previousSibling;
            }
            relatedWidgetWrapper.insertBefore(link, previousSibling.nextSibling);
        }
    }

    // Return the link, which we'll use in the disable and enable functions
    return link;
}

// Either enable or disable widget buttons when select is clicked. Action (enable or disable) taken depends on the count
// of selected items in selectElement. If exactly one item is selected, buttons are enabled, and urls for the buttons are
// associated with the selected item
function handleSelectClick(selectElement, changeLink, deleteLink, viewLink) {

    // If one item is selected (across selectElement and relatedSelectElement), enable buttons; otherwise, disable them
    if (selectElement.selectedOptions.length === 1) {
        // enable buttons for selected item in selectElement
        enableRelatedWidgetButtons(changeLink, deleteLink, viewLink, selectElement.selectedOptions[0].value, selectElement.selectedOptions[0].text);
    } else {
        disableRelatedWidgetButtons(changeLink, deleteLink, viewLink);
    }
}

// return true if there exist elements on the page with classname of delete-related.
// presence of one or more of these elements indicates user has permission to delete
function hasDeletePermissionOnPage() {
    return document.querySelector('.delete-related') != null
}

function disableRelatedWidgetButtons(changeLink, deleteLink, viewLink) {
    changeLink.removeAttribute('href');
    changeLink.setAttribute('title', changeLink.getAttribute('title-template'));
    if (deleteLink) {
        deleteLink.removeAttribute('href');
        deleteLink.setAttribute('title', deleteLink.getAttribute('title-template'));
    }
    viewLink.removeAttribute('href');
    viewLink.setAttribute('title', viewLink.getAttribute('title-template'));
}

function enableRelatedWidgetButtons(changeLink, deleteLink, viewLink, elementPk, elementText) {
    changeLink.setAttribute('href', changeLink.getAttribute('data-href-template').replace('__fk__', elementPk));
    changeLink.setAttribute('title', changeLink.getAttribute('title-template').replace('selected item', elementText));
    if (deleteLink) {
        deleteLink.setAttribute('href', deleteLink.getAttribute('data-href-template').replace('__fk__', elementPk));
        deleteLink.setAttribute('title', deleteLink.getAttribute('title-template').replace('selected item', elementText));
    }
    viewLink.setAttribute('href', viewLink.getAttribute('data-href-template').replace('__fk__', elementPk));
    viewLink.setAttribute('title', viewLink.getAttribute('title-template').replace('selected item', elementText));
}

/** An IIFE for admin in DjangoAdmin to listen to changes on the domain request
 * status select amd to show/hide the rejection reason
*/
(function (){
    let rejectionReasonFormGroup = document.querySelector('.field-rejection_reason')

    if (rejectionReasonFormGroup) {
        let statusSelect = document.getElementById('id_status')

        // Initial handling of rejectionReasonFormGroup display
        if (statusSelect.value != 'rejected')
            rejectionReasonFormGroup.style.display = 'none';

        // Listen to change events and handle rejectionReasonFormGroup display, then save status to session storage
        statusSelect.addEventListener('change', function() {
            if (statusSelect.value == 'rejected') {
                rejectionReasonFormGroup.style.display = 'block';
                sessionStorage.removeItem('hideRejectionReason');
            } else {
                rejectionReasonFormGroup.style.display = 'none';
                sessionStorage.setItem('hideRejectionReason', 'true');
            }
        });
    }

    // Listen to Back/Forward button navigation and handle rejectionReasonFormGroup display based on session storage

    // When you navigate using forward/back after changing status but not saving, when you land back on the DA page the
    // status select will say (for example) Rejected but the selected option can be something else. To manage the show/hide
    // accurately for this edge case, we use cache and test for the back/forward navigation.
    const observer = new PerformanceObserver((list) => {
        list.getEntries().forEach((entry) => {
          if (entry.type === "back_forward") {
            if (sessionStorage.getItem('hideRejectionReason'))
                document.querySelector('.field-rejection_reason').style.display = 'none';
            else
                document.querySelector('.field-rejection_reason').style.display = 'block';
          }
        });
    });
    observer.observe({ type: "navigation" });
})();

/** An IIFE for toggling the submit bar on domain request forms
*/
(function (){
    // Get a reference to the button element
    const toggleButton = document.getElementById('submitRowToggle');
    const submitRowWrapper = document.querySelector('.submit-row-wrapper');

    if (toggleButton) {
        // Add event listener to toggle the class and update content on click
        toggleButton.addEventListener('click', function() {
            // Toggle the 'collapsed' class on the bar
            submitRowWrapper.classList.toggle('submit-row-wrapper--collapsed');

            // Get a reference to the span element inside the button
            const spanElement = this.querySelector('span');

            // Get a reference to the use element inside the button
            const useElement = this.querySelector('use');

            // Check if the span element text is 'Hide'
            if (spanElement.textContent.trim() === 'Hide') {
                // Update the span element text to 'Show'
                spanElement.textContent = 'Show';

                // Update the xlink:href attribute to expand_more
                useElement.setAttribute('xlink:href', '/public/img/sprite.svg#expand_less');
            } else {
                // Update the span element text to 'Hide'
                spanElement.textContent = 'Hide';

                // Update the xlink:href attribute to expand_less
                useElement.setAttribute('xlink:href', '/public/img/sprite.svg#expand_more');
            }
        });

        // We have a scroll indicator at the end of the page.
        // Observe it. Once it gets on screen, test to see if the row is collapsed.
        // If it is, expand it.
        const targetElement = document.querySelector(".scroll-indicator");
        const options = {
            threshold: 1
        };
        // Create a new Intersection Observer
        const observer = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    // Refresh reference to submit row wrapper and check if it's collapsed
                    if (document.querySelector('.submit-row-wrapper').classList.contains('submit-row-wrapper--collapsed')) {
                        toggleButton.click();
                    }
                }
            });
        }, options);
        observer.observe(targetElement);
    }
})();
