/**
 * Initializes buttons to behave like links by navigating to their data-url attribute
 * Example usage: <button class="use-button-as-link" data-url="/some/path">Click me</button>
 */
export function initButtonLinks() {
    document.querySelectorAll('button.use-button-as-link').forEach(button => {
        button.addEventListener('click', function() {
            // Equivalent to button.getAttribute("data-href")
            const href = this.dataset.href;
            if (href) {
                window.location.href = href;
            }
        });
    });
}
