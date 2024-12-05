/**
 * A function that appends target="_blank" to the domain_form buttons
*/

/** Either sets attribute target="_blank" to a given element, or removes it */
function openInNewTab(el, removeAttribute = false){
    if(removeAttribute){
        el.setAttribute("target", "_blank");
    }else{
        el.removeAttribute("target", "_blank");
    }
};

/**
On mouseover, appends target="_blank" on domain_form under the Domain page.
The reason for this is that the template has a form that contains multiple buttons.
The structure of that template complicates seperating those buttons 
out of the form (while maintaining the same position on the page).
However, if we want to open one of those submit actions to a new tab - 
such as the manage domain button - we need to dynamically append target.
As there is no built-in django method which handles this, we do it here. 
*/
export function initDomainFormTargetBlankButtons() {
    let domainFormElement = document.getElementById("domain_form");
    let domainSubmitButton = document.getElementById("manageDomainSubmitButton");
    if(domainSubmitButton && domainFormElement){
        domainSubmitButton.addEventListener("mouseover", () => openInNewTab(domainFormElement, true));
        domainSubmitButton.addEventListener("mouseout", () => openInNewTab(domainFormElement, false));
    }
}
