// Function to check for the existence of the "to" select list element in the DOM, and if and when found,
// initialize the associated widget
function checkToListThenInitWidget(toListId, attempts) {
    let toList = document.getElementById(toListId);
    attempts++;

    if (attempts < 12) {
        if (toList) {
            // toList found, handle it
            // Then get fromList and handle it
            initializeWidgetOnList(toList, ".selector-chosen");
            let fromList = toList.closest('.selector').querySelector(".selector-available select");
            initializeWidgetOnList(fromList, ".selector-available");
        } else {
            // Element not found, check again after a delay
            setTimeout(() => checkToListThenInitWidget(toListId, attempts), 300); // Check every 300 milliseconds
        }
    }
}

// Initialize the widget:
// Replace h2 with more semantic h3
function initializeWidgetOnList(list, parentId) {    
    if (list) {
        // Get h2 and its container
        const parentElement = list.closest(parentId);
        const h2Element = parentElement.querySelector('h2');

        // One last check
        if (parentElement && h2Element) {
            // Create a new <h3> element
            const h3Element = document.createElement('h3');

            // Copy the text content from the <h2> element to the <h3> element
            h3Element.textContent = h2Element.textContent;

            // Find the nested <span> element inside the <h2>
            const nestedSpan = h2Element.querySelector('span[class][title]');

            // If the nested <span> element exists
            if (nestedSpan) {
                // Create a new <span> element
                const newSpan = document.createElement('span');

                // Copy the class and title attributes from the nested <span> element
                newSpan.className = nestedSpan.className;
                newSpan.title = nestedSpan.title;

                // Append the new <span> element to the <h3> element
                h3Element.appendChild(newSpan);
            }

            // Replace the <h2> element with the new <h3> element
            parentElement.replaceChild(h3Element, h2Element);
        }
    }
}

/**
 *
 * An IIFE to listen to changes on filter_horizontal and enable or disable the change/delete/view buttons as applicable
 *
 */
export function initFilterHorizontalWidget() {
    // Initialize custom filter_horizontal widgets; each widget has a "from" select list
    // and a "to" select list; initialization is based off of the presence of the
    // "to" select list
    checkToListThenInitWidget('id_groups_to', 0);
    checkToListThenInitWidget('id_user_permissions_to', 0);
    checkToListThenInitWidget('id_portfolio_roles_to', 0);
    checkToListThenInitWidget('id_portfolio_additional_permissions_to', 0);
}
