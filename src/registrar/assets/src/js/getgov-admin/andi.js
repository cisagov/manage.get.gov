export function initAriaInjections() {
    console.log("FIRED")
    document.addEventListener('DOMContentLoaded', function () {
        // Find all spans with "--aria-description" in their id
        const descriptionSpans = document.querySelectorAll('span[id*="--aria-description"]');

        // Iterate through each span to add aria-describedby
        descriptionSpans.forEach(function(span) {
            // Extract the base ID from the span's id (remove "--aria-description" part)
            const fieldId = span.id.replace('--aria-description', '');

            // Find the field element with the corresponding ID
            const field = document.getElementById(fieldId);

            // If the field exists, set the aria-describedby attribute
            if (field) {
                let select2ElementDetected = false
                if (field.classList.contains('admin-autocomplete')) {
                    console.log("select2---> select2-"+${fieldId}+"-container")
                    // If it's a Select2 component, find the rendered span inside Select2
                    const select2Span = field.querySelector('.select2-selection');
                    if (select2Span) {
                        console.log("set select2 aria")
                        select2Span.setAttribute('aria-describedby', span.id);
                        select2ElementDetected=true
                    }
                } 
                if (!select2ElementDetected)
                {
                    // Otherwise, set aria-describedby directly on the field
                    field.setAttribute('aria-describedby', span.id);
                }
            }
        });
    });
}