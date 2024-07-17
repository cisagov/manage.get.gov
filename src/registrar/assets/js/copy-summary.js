
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('copy-summary-btn').addEventListener('click', function() {
        // Generate the summary text
        const organizationType = document.getElementById('id_organization_type').value;
        const requestedDomain = document.getElementById('id_requested_domain').value;
        const existingWebsites = Array.from(document.querySelectorAll('#id_current_websites')).map(el => el.text).join(', ');
        const alternativeDomains = Array.from(document.querySelectorAll('#id_alternative_domains')).map(el => el.text).join(', ');
        const submitter = document.getElementById('id_submitter').value;
        const seniorOfficial = document.getElementById('id_senior_official').value;
        const otherContacts = Array.from(document.querySelectorAll('#id_other_contacts option:checked')).map(el => el.text).join('\n* ');

        const summary = `*Recommendation:*\n\n` +
                        `*Organization Type:* ${organizationType}\n\n` +
                        `*Requested Domain:* ${requestedDomain}\n\n` +
                        `*Existing website(s):*\n${existingWebsites}\n\n` +
                        `*Rationale:*\n\n` +
                        `*Alternate Domain(s):*\n* ${alternativeDomains.split(', ').join('\n* ')}\n\n` +
                        `*Submitter:*\n\n* ${submitter}\n\n` +
                        `*Senior Official:*\n\n* ${seniorOfficial}\n\n` +
                        `*Additional Contact(s):*\n\n* ${otherContacts}\n\n`;

        // Create a temporary textarea element to hold the summary
        const textArea = document.createElement('textarea');
        textArea.value = summary;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);

        alert('Summary copied to clipboard!');
        alert("hello");
    });
});
