export function hideElement(element) {
    element.classList.add('display-none');
};
  
export function showElement(element) {
    element.classList.remove('display-none');
};

/**
   * Helper function that scrolls to an element
   * @param {string} attributeName - The string "class" or "id"
   * @param {string} attributeValue - The class or id name
   */
export function scrollToElement(attributeName, attributeValue) {
    let targetEl = null;
  
    if (attributeName === 'class') {
        targetEl = document.getElementsByClassName(attributeValue)[0];
    } else if (attributeName === 'id') {
        targetEl = document.getElementById(attributeValue);
    } else {
        console.error('Error: unknown attribute name provided.');
        return; // Exit the function if an invalid attributeName is provided
    }
  
    if (targetEl) {
        const rect = targetEl.getBoundingClientRect();
        const scrollTop = window.scrollY || document.documentElement.scrollTop;
        window.scrollTo({
            top: rect.top + scrollTop,
            behavior: 'smooth' // Optional: for smooth scrolling
        });
    }
}

/**
 * Toggles expand_more / expand_more svgs in buttons or anchors
 * @param {Element} element - DOM element
 */
export function toggleCaret(element) {
    // Get a reference to the use element inside the button
    const useElement = element.querySelector('use');
    // Check if the span element text is 'Hide'
    if (useElement.getAttribute('xlink:href') === '/public/img/sprite.svg#expand_more') {
        // Update the xlink:href attribute to expand_more
        useElement.setAttribute('xlink:href', '/public/img/sprite.svg#expand_less');
    } else {
        // Update the xlink:href attribute to expand_less
        useElement.setAttribute('xlink:href', '/public/img/sprite.svg#expand_more');
    }
}

/**
   * Slow down event handlers by limiting how frequently they fire.
   *
   * A wait period must occur with no activity (activity means "this
   * debounce function being called") before the handler is invoked.
   *
   * @param {Function} handler - any JS function
   * @param {number} cooldown - the wait period, in milliseconds
   */
export function debounce(handler, cooldown=600) {
    let timeout;
    return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => handler.apply(context, args), cooldown);
    }
}

// Adds or removes a boolean from our session
export function addOrRemoveSessionBoolean(name, add){
    if (add) {
        sessionStorage.setItem(name, "true");
    }else {
        sessionStorage.removeItem(name); 
    }
}
