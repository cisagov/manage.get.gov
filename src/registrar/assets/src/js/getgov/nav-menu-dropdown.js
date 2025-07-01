/* 
Initializes event listeners for custom dropdowns on secondary navbar
since USWDS secondary navbar currently does not support dropdown menus.
*/
export function initializeNavMenuEventListener(menuButtonId, menuContentsId) {
    document.getElementById(menuButtonId).setAttribute('aria-expanded', false);

    document.getElementById(menuButtonId).addEventListener('click', function() {
        const expanded = this.getAttribute('aria-expanded') == 'true';
        this.setAttribute('aria-expanded', !expanded);
        document.getElementById(menuContentsId).hidden = expanded;
    })
}