/*
This function intercepts all select2 dropdowns and adds aria content.
It relies on an override in detail_table_fieldset.html that provides
a span with a corresponding id for aria-describedby content.

This allows us to avoid overriding aria-label, which is used by select2
to send the current dropdown selection to ANDI.
*/
export function initAriaInjectionsForSelect2Dropdowns() {
    document.addEventListener('DOMContentLoaded', function () {
        // Find all spans with "--aria-description" in their id
        const descriptionSpans = document.querySelectorAll('span[id*="--aria-description"]');

        descriptionSpans.forEach(function (span) {
            // Extract the base ID from the span's id (remove "--aria-description")
            const fieldId = span.id.replace('--aria-description', '');
            const field = document.getElementById(fieldId);

            if (field) {
                // If Select2 is already initialized, apply aria-describedby immediately
                if (field.classList.contains('select2-hidden-accessible')) {
                    applyAriaDescribedBy(field, span.id);
                    return;
                }

                // Use MutationObserver to detect Select2 initialization
                const observer = new MutationObserver(function (mutations) {
                    if (document.getElementById(fieldId)?.classList.contains("select2-hidden-accessible")) {
                        applyAriaDescribedBy(field, span.id);
                        observer.disconnect(); // Stop observing after applying attributes
                    }
                });

                observer.observe(document.body, {
                    childList: true,
                    subtree: true
                });
            }
        });

        // Function to apply aria-describedby to Select2 UI
        function applyAriaDescribedBy(field, descriptionId) {
            let select2ElementDetected = false;
            const select2Id = "select2-" + field.id + "-container";

            // Find the Select2 selection box
            const select2SpanThatTriggersAria = document.querySelector(`span[aria-labelledby='${select2Id}']`);

            if (select2SpanThatTriggersAria) {
                select2SpanThatTriggersAria.setAttribute('aria-describedby', descriptionId);
                select2ElementDetected = true;
            }

            // If no Select2 component was detected, apply aria-describedby directly to the field
            if (!select2ElementDetected) {
                field.setAttribute('aria-describedby', descriptionId);
            }
        }
    });
}