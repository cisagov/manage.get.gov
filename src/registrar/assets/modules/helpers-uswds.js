/**
 * Initialize USWDS tooltips by calling initialization method.  Requires that uswds-edited.js
 * be loaded before get-gov.js.  uswds-edited.js adds the tooltip module to the window to be
 * accessible directly in get-gov.js
 * 
 */
export function initializeTooltips() {
    function checkTooltip() {
      // Check that the tooltip library is loaded, and if not, wait and retry
      if (window.tooltip && typeof window.tooltip.init === 'function') {
          window.tooltip.init();
      } else {
          // Retry after a short delay
          setTimeout(checkTooltip, 100);
      }
    }
    checkTooltip();
  }
  
/**
 * Initialize USWDS modals by calling on method.  Requires that uswds-edited.js be loaded
 * before get-gov.js.  uswds-edited.js adds the modal module to the window to be accessible
 * directly in get-gov.js.
 * initializeModals adds modal-related DOM elements, based on other DOM elements existing in 
 * the page.  It needs to be called only once for any particular DOM element; otherwise, it
 * will initialize improperly.  Therefore, if DOM elements change dynamically and include
 * DOM elements with modal classes, unloadModals needs to be called before initializeModals.
 * 
 */
export function initializeModals() {
    window.modal.on();
}

/**
 * Unload existing USWDS modals by calling off method.  Requires that uswds-edited.js be
 * loaded before get-gov.js.  uswds-edited.js adds the modal module to the window to be
 * accessible directly in get-gov.js.
 * See note above with regards to calling this method relative to initializeModals.
 * 
 */
export function unloadModals() {
    window.modal.off();
}
