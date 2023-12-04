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

/**
 * An IIFE to listen to changes on filter_horizontal and enable or disable the change/delete/view buttons as applicable
 *
 */
(function extendFilterHorizontalWidgets() {
    // Grab a list of our custom filter_horizontal widgets
    let filterHorizontalList = [];
    checkElementThenAddToList('id_other_contacts_to', filterHorizontalList, 0);
    checkElementThenAddToList('id_domain_info-0-other_contacts_to', filterHorizontalList, 0);
    checkElementThenAddToList('id_current_websites_to', filterHorizontalList, 0);
    checkElementThenAddToList('id_alternative_domains_to', filterHorizontalList, 0);
})();

// Function to check for the existence of the element
function checkElementThenAddToList(id, listOfElements, attempts) {
    let dynamicElement = document.getElementById(id);
    attempts++;

    if (attempts < 6) {
        if ((dynamicElement !== null)) {
            // Element found, handle it
            // Add an event listener on the element
            // Add disabled buttons on the element's great-grandparent
            customizeSelectElement(dynamicElement, id);
        } else {
            // Element not found, check again after a delay
            setTimeout(() => checkElementThenAddToList(id, listOfElements, attempts), 1000); // Check every 1000 milliseconds (1 second)
        }
    }
}

function customizeSelectElement(el, elId) {
    let changeLink = createAndCustomizeLink(
        el,
        elId,
        'related-widget-wrapper-link change-related',
        'Change selected item',
        '/public/admin/img/icon-changelink.svg',
        'Change',
        {
            'contacts': '/admin/registrar/contact/__fk__/change/?_to_field=id&_popup=1',
            'websites': '/admin/registrar/website/__fk__/change/?_to_field=id&_popup=1',
            'alternative_domains': '/admin/registrar/website/__fk__/change/?_to_field=id&_popup=1',
        },
        true,
        0
    );

    let deleteLink = createAndCustomizeLink(
        el,
        elId,
        'related-widget-wrapper-link delete-related',
        'Delete selected item',
        '/public/admin/img/icon-deletelink.svg',
        'Delete',
        {
            'contacts': '/admin/registrar/contact/__fk__/delete/?_to_field=id&amp;_popup=1',
            'websites': '/admin/registrar/website/__fk__/delete/?_to_field=id&_popup=1',
            'alternative_domains': '/admin/registrar/website/__fk__/delete/?_to_field=id&_popup=1',
        },
        true,
        2
    );

    let viewLink = createAndCustomizeLink(
        el,
        elId,
        'related-widget-wrapper-link view-related',
        'View selected item',
        '/public/admin/img/icon-viewlink.svg',
        'View',
        {
            'contacts': '/admin/registrar/contact/__fk__/change/?_to_field=id',
            'websites': '/admin/registrar/website/__fk__/change/?_to_field=id',
            'alternative_domains': '/admin/registrar/website/__fk__/change/?_to_field=id',
        },
        false,
        3
    );

    let fromList = el.closest('.selector').querySelector(".selector-available select");

    fromList.addEventListener('click', function(event) {
        handleSelectClick(event, fromList, changeLink, deleteLink, viewLink);
    });
    
    el.addEventListener('click', function(event) {
        handleSelectClick(event, el, changeLink, deleteLink, viewLink);
    });
    
    // Disable buttons when the selectors are interated with (items are moved from one column to the other)
    let selectorButtons = [];
    selectorButtons.push(el.closest(".selector").querySelector(".selector-chooseall"));
    selectorButtons.push(el.closest(".selector").querySelector(".selector-add"));
    selectorButtons.push(el.closest(".selector").querySelector(".selector-remove"));

    selectorButtons.forEach((selector) => {
        selector.addEventListener("click", ()=>{disableRelatedWidgetButtons(changeLink, deleteLink, viewLink)});
      });
}

function createAndCustomizeLink(selectEl, selectElId, className, title, imgSrc, imgAlt, dataMappings, dataPopup, position) {
    // Create a link element
    var link = document.createElement('a');

    // Set class attribute for the link
    link.className = className;

    // Set id
    // Add 'change_' to the beginning of the string
    let modifiedLinkString = className.split('-')[0] + '_' + selectElId;
    // Remove '_to' from the end of the string
    modifiedLinkString = modifiedLinkString.replace('_to', '');
    link.id = modifiedLinkString;

    // Set data-href-template
    for (const [idPattern, template] of Object.entries(dataMappings)) {
        if (selectElId.includes(idPattern)) {
            link.setAttribute('data-href-template', template);
            break; // Stop checking once a match is found
        }
    }

    if (dataPopup)
        link.setAttribute('data-popup', 'yes');
    
    link.title = title;

    // Create an 'img' element
    var img = document.createElement('img');

    // Set attributes for the new image
    img.src = imgSrc;
    img.alt = imgAlt;

    // Append the image to the link
    link.appendChild(img);

    // Insert the link at the specified position
    selectEl.closest('.related-widget-wrapper').insertBefore(link, selectEl.closest('.related-widget-wrapper').children[position]);

    // Return the link, which we'll use in the disable and enable functions
    return link;
}

function handleSelectClick(event, selectElement, changeLink, deleteLink, viewLink) {
    // Access the target element that was clicked
    var clickedElement = event.target;

    // If one item is selected, enable buttons; otherwise, disable them
    if (selectElement.selectedOptions.length === 1) {
        enableRelatedWidgetButtons(changeLink, deleteLink, viewLink, clickedElement.value);
    } else {
        disableRelatedWidgetButtons(changeLink, deleteLink, viewLink);
    }
}

function disableRelatedWidgetButtons(changeLink, deleteLink, viewLink) {
    changeLink.removeAttribute('href');
    deleteLink.removeAttribute('href');
    viewLink.removeAttribute('href');
}

function enableRelatedWidgetButtons(changeLink, deleteLink, viewLink, elementPk) {
    changeLink.setAttribute('href', changeLink.getAttribute('data-href-template').replace('__fk__', elementPk));
    deleteLink.setAttribute('href', deleteLink.getAttribute('data-href-template').replace('__fk__', elementPk));
    viewLink.setAttribute('href', viewLink.getAttribute('data-href-template').replace('__fk__', elementPk));
}
