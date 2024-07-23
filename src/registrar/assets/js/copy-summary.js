
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('copy-summary-btn').addEventListener('click', function() {
        // Generate the summary text

        const organizationTypeElement = document.getElementById('id_organization_type');
        const organizationType = organizationTypeElement.options[organizationTypeElement.selectedIndex].text;

        const alternativeDomainsDiv = document.querySelector('.form-row.field-alternative_domains .readonly');
        const alternativeDomainslinks = alternativeDomainsDiv.querySelectorAll('a');
        const alternativeDomains = Array.from(alternativeDomainslinks).map(link => link.textContent);

        const existingWebsitesDiv = document.querySelector('.form-row.field-current_websites .readonly');
        const existingWebsiteslinks = existingWebsitesDiv.querySelectorAll('a');
        const existingWebsites = Array.from(existingWebsiteslinks).map(link => link.textContent);

        const otherContactsDiv = document.querySelector('.form-row.field-other_contacts .readonly');
        const otherContactslinks = otherContactsDiv.querySelectorAll('a');
        const otherContacts = Array.from(otherContactslinks).map(link => link.textContent);

        const requestedDomainElement = document.getElementById('id_requested_domain');
        const requestedDomain = requestedDomainElement.options[requestedDomainElement.selectedIndex].text;

        const submitterElement = document.getElementById('id_submitter');
        const submitter = submitterElement.options[submitterElement.selectedIndex].text;

        const seniorOfficialElement = document.getElementById('id_senior_official');
        const seniorOfficial = seniorOfficialElement.options[seniorOfficialElement.selectedIndex].text;

        const summary = `<strong>Recommendation:</strong></br>` +
                        `<strong>Organization Type:</strong> ${organizationType}</br>` +
                        `<strong>Requested Domain:</strong> ${requestedDomain}</br>` +
                        `<strong>Existing website(s):</strong> ${existingWebsites.join('</br>')}</br>` +
                        `<strong>Rationale:</strong></br>` +
                        `<strong>Alternate Domain(s):</strong> ${alternativeDomains.join('</br>')}</br>` +
                        `<strong>Submitter:</strong> ${submitter}</br>` +
                        `<strong>Senior Official:</strong> ${seniorOfficial}</br>` +
                        `<strong>Additional Contact(s):</strong> ${otherContacts.join('</br>')}</br>`;

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
