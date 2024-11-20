export function hideElement(element) {
    console.log(element)
    element.classList.add('display-none');
};
  
export function showElement(element) {
    element.classList.remove('display-none');
};

// Adds or removes a boolean from our session
export function addOrRemoveSessionBoolean(name, add){
    if (add) {
        sessionStorage.setItem(name, "true");
    }else {
        sessionStorage.removeItem(name); 
    }
}
