
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('copy-summary-btn').addEventListener('click', function() {
        /// Generate a rich HTML summary text and copy to clipboard

        //------ Organization Type
        const organizationTypeElement = document.getElementById('id_organization_type');
        const organizationType = organizationTypeElement.options[organizationTypeElement.selectedIndex].text;

        //------ Alternative Domains
        const alternativeDomainsDiv = document.querySelector('.form-row.field-alternative_domains .readonly');
        const alternativeDomainslinks = alternativeDomainsDiv.querySelectorAll('a');
        const alternativeDomains = Array.from(alternativeDomainslinks).map(link => link.textContent);

        //------ Existing Websites
        const existingWebsitesDiv = document.querySelector('.form-row.field-current_websites .readonly');
        const existingWebsiteslinks = existingWebsitesDiv.querySelectorAll('a');
        const existingWebsites = Array.from(existingWebsiteslinks).map(link => link.textContent);

        //------ Additional Contacts
        // 1 - Create a hyperlinks map so we can display contact details and also link to the contact
        const otherContactsDiv = document.querySelector('.form-row.field-other_contacts .readonly');
        let otherContactLinks = [];
        if (otherContactsDiv) {
            otherContactLinks = otherContactsDiv.querySelectorAll('a');
            const nameToUrlMap = {};
            otherContactLinks.forEach(link => {
              const name = link.textContent.trim();
              const url = link.href;
              nameToUrlMap[name] = url;
            });
        }
    
        // 2 - Iterate through contact details and assemble html for summary
        let otherContactsSummary = ""
        // Get the table rows of contact details
        // Select all contact elements
        const contacts = document.querySelectorAll('.dja-detail-list dl');

        // Iterate through each contact element
        contacts.forEach(contact => {
            const name = contact.querySelector('a#contact_info_name').innerText;
            const title = contact.querySelector('span#contact_info_title').innerText;
            const email = contact.querySelector('span#contact_info_email').innerText;
            const phone = contact.querySelector('span#contact_info_phone').innerText;

            const url = nameToUrlMap[name] || '#';
            // Format the contact information
            const listItem = document.createElement('li');
            listItem.innerHTML = `<a href="${url}">${name}</a>, ${title}, ${email}, ${phone}`;
            bulletList.appendChild(listItem);
            });
            otherContactsSummary += bulletList.outerHTML
        });


        //------ Requested Domains
        const requestedDomainElement = document.getElementById('id_requested_domain');
        const requestedDomain = requestedDomainElement.options[requestedDomainElement.selectedIndex].text;

        //------ Submitter
        // Function to extract text by ID and handle missing elements
        function extractTextById(id, divElement) {
            if (divElement) {
                const element = divElement.querySelector(`#${id}`);
                return element ? ", " + element.textContent.trim() : '';
            }
            return '';
        }
        // Extract the submitter name, title, email, and phone number
        const submitterDiv = document.querySelector('.form-row.field-submitter');
        const submitterNameElement = document.getElementById('id_submitter');
        const submitterName = submitterNameElement.options[submitterNameElement.selectedIndex].text;
        const submitterTitle = extractTextById('contact_info_title', submitterDiv);
        const submitterEmail = extractTextById('contact_info_email', submitterDiv);
        const submitterPhone = extractTextById('contact_info_phone', submitterDiv);
        let submitterInfo = `${submitterName}${submitterTitle}${submitterEmail}${submitterPhone}`;


        //------ Senior Official
        const seniorOfficialDiv = document.querySelector('.form-row.field-senior_official');
        const seniorOfficialElement = document.getElementById('id_senior_official');
        const seniorOfficialName = seniorOfficialElement.options[seniorOfficialElement.selectedIndex].text;
        const seniorOfficialTitle = extractTextById('contact_info_title', seniorOfficialDiv);
        const seniorOfficialEmail = extractTextById('contact_info_email', seniorOfficialDiv);
        const seniorOfficialPhone = extractTextById('contact_info_phone', seniorOfficialDiv);
        let seniorOfficialInfo = `${seniorOfficialName}${seniorOfficialTitle}${seniorOfficialEmail}${seniorOfficialPhone}`;

        const summary = `<strong>Recommendation:</strong></br>` +
                        `<strong>Organization Type:</strong> ${organizationType}</br>` +
                        `<strong>Requested Domain:</strong> ${requestedDomain}</br>` +
                        `<strong>Existing website(s):</strong> ${existingWebsites.join(', ')}</br>` +
                        `<strong>Rationale:</strong></br>` +
                        `<strong>Alternate Domain(s):</strong> ${alternativeDomains.join(', ')}</br>` +
                        `<strong>Submitter:</strong> ${submitterInfo}</br>` +
                        `<strong>Senior Official:</strong> ${seniorOfficialInfo}</br>` +
                        `<strong>Additional Contact(s):</strong> ${otherContactsSummary}</br>`;

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
