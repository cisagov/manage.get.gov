
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('copy-summary-btn').addEventListener('click', function() {
        // Generate the summary text
        const organizationType = document.getElementById('id_organization_type').value;
        const requestedDomain = document.getElementById('id_requested_domain').value;
        const existingWebsites = Array.from(document.querySelectorAll('#id_current_websites')).map(el => el.text).join(', ');
        const alternativeDomains = Array.from(document.querySelectorAll('#id_alternative_domains')).map(el => el.text).join(', ');
        const submitter = document.getElementById('id_submitter').value;
        const seniorOfficial = document.getElementById('id_senior_official').value;
        const otherContacts = Array.from(document.querySelectorAll('#id_other_contacts option:checked')).map(el => el.text).join('\n ');

        const summary = `<strong>Recommendation:</strong></br>` +
                        `<strong>Organization Type:</strong> ${organizationType}</br>` +
                        `<strong>Requested Domain:</strong> ${requestedDomain}</br>` +
                        `<strong>Existing website(s):</strong> ${existingWebsites}</br>` +
                        `<strong>Rationale:</strong>` +
                        `<strong>Alternate Domain(s):</strong> ${alternativeDomains.split(', ').join('\n ')}</br>` +
                        `<strong>Submitter:</strong> ${submitter}</br>` +
                        `<strong>Senior Official:</strong> ${seniorOfficial}</br>` +
                        `<strong>Additional Contact(s):</strong> ${otherContacts}</br>`;

        // Create a temporary element
        let tempElement = document.createElement('div');
        tempElement.innerHTML = summary;
        // Append the element to the body
        document.body.appendChild(tempElement);

        // Use the Selection and Range APIs to select the element's content
        let range = document.createRange();
        range.selectNodeContents(tempElement);
        let selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);

        // Use the Clipboard API to write the selected HTML content to the clipboard
        navigator.clipboard.write([
            new ClipboardItem({
                'text/html': new Blob([tempElement.innerHTML], { type: 'text/html' })
            })
        ]).then(() => {
            console.log('Bold text copied to clipboard successfully!');
        }).catch(err => {
            console.error('Failed to copy text: ', err);
        });
        document.body.removeChild(tempElement); 

        alert('Summary copied to clipboard!');
    });
});
