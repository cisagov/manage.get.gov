/*
This function intercepts all select2 dropdowns and adds aria content.
It relies on an override in detail_table_fieldset.html that provides
a span with a corresponding id for aria-describedby content.

This allows us to avoid overriding aria-label, which is used by select2
to send the current dropdown selection to ANDI
*/
export function initAriaInjections() {
    document.addEventListener('DOMContentLoaded', function () {
        // Set timeout so this fires after select2.js finishes adding to the DOM
        setTimeout(function () {
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
                        const select2Id="select2-"+fieldId+"-container"
                        console.log("select2---> "+select2Id)
                        // If it's a Select2 component, find the rendered span inside Select2
                        const select2SpanThatTriggersAria = document.querySelector("span[aria-labelledby='"+select2Id+"']");
                        const select2SpanThatHoldsSelection = document.getElementById(select2Id)
                        if (select2SpanThatTriggersAria) {
                            console.log("set select2 aria")
                            select2SpanThatTriggersAria.setAttribute('aria-describedby', span.id);
                            // select2SpanThatTriggersAria.setAttribute('aria-labelledby', select2Id);
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
        }, 500);
    });
}