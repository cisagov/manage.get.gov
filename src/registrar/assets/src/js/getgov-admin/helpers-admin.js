export function hideElement(element) {
    if (element) {
        element.classList.add('display-none');
    } else {
        console.warn('Called hideElement on a null or undefined element');
    }
};
  
export function showElement(element) {
    if (element) {
        element.classList.remove('display-none');
    } else {
        console.warn('Called showElement on a null or undefined element');
    }
};

// Adds or removes a boolean from our session
export function addOrRemoveSessionBoolean(name, add){
    if (add) {
        sessionStorage.setItem(name, "true");
    } else {
        sessionStorage.removeItem(name); 
    }
}

export function getParameterByName(name, url) {
    if (!url) url = window.location.href;
    name = name.replace(/[\[\]]/g, '\\$&');
    var regex = new RegExp('[?&]' + name + '(=([^&#]*)|&|#|$)'),
        results = regex.exec(url);
    if (!results) return null;
    if (!results[2]) return '';
    return decodeURIComponent(results[2].replace(/\+/g, ' '));
}
