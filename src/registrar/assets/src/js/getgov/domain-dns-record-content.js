console.log('domain-dns-record-content.js loaded')

export function initDynamicDNSRecordFormFields() {
    const typeField = document.getElementById('id_type');
    const contentField = document.getElementById('id_content');
    const contentLabel = document.querySelector('label[for=id_content]');
    const contentHelp = document.getElementById('id_content_helptext');

    if (!typeField || !contentField) return;

    typeField.addEventListener('change', function (){
        const selectedType = this.value;

        if (selectedType === 'A') {
            if (contentLabel) contentLabel.textContent = 'IPv4 Address';
            if (contentHelp) contentHelp.textContent = 'Example: 192.0.2.10';
        } else if (selectedType === 'AAAA') {
            if (contentLabel) contentLabel.textContent = 'IPv6 Address';
            if (contentHelp) contentHelp.textContent = 'Example: 2008::db8:1';
        } 
        else {
            if (contentLabel) contentLabel.textContent = 'Content Label';
            if (contentHelp) contentHelp.textContent = 'Default help text';
        }
    });

    if (typeField.value) {
        typeField.dispatchEvent(new Event('change'));
    }
}