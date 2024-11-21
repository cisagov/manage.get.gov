/**
 * Helper function to get the CSRF token from the cookie
 *
*/
export function getCsrfToken() {
    return document.querySelector('input[name="csrfmiddlewaretoken"]').value;
}
  