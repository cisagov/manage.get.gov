import { BaseTable } from './table-base.js';
import { uswdsInitializeTooltips } from './helpers-uswds.js';

export class DomainsTable extends BaseTable {

  constructor() {
    super('domain');
    this.currentSortBy = 'name';
  }
  getBaseUrl() {
    return document.getElementById("get_domains_json_url");
  }
  getDataObjects(data) {
    return data.domains;
  }
  addRow(dataObject, tbody, customTableOptions) {
    const domain = dataObject;
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    const expirationDate = domain.expiration_date ? new Date(domain.expiration_date) : null;
    const expirationDateFormatted = expirationDate ? expirationDate.toLocaleDateString('en-US', options) : '';
    const expirationDateSortValue = expirationDate ? expirationDate.getTime() : '';
    const actionUrl = domain.action_url;
    const suborganization = domain.domain_info__sub_organization ? domain.domain_info__sub_organization : '⎯';

    const row = document.createElement('tr');

    let markupForSuborganizationRow = '';

    if (this.portfolioValue) {
      markupForSuborganizationRow = `
        <td data-label="Suborganization">
            <span class="text-wrap" aria-label="${domain.suborganization ? suborganization : 'No suborganization'}">${suborganization}</span>
        </td>
      `
    }
    const isExpiring = domain.state_display === "Expiring soon"
    const iconType = isExpiring ? "error_outline" : "info_outline";
    const iconColor = isExpiring ? "text-secondary-vivid" : "text-accent-cool"
    row.innerHTML = `
      <th scope="row" role="rowheader" data-label="Domain name">
        ${domain.name}
      </th>
      <td data-sort-value="${expirationDateSortValue}" data-label="Expires">
        ${expirationDateFormatted}
      </td>
      <td data-label="Status">
        ${domain.state_display}
        <svg 
        class="usa-icon usa-tooltip usa-tooltip--registrar text-middle margin-bottom-05 ${iconColor} no-click-outline-and-cursor-help" 
        data-position="top"
          title="${domain.get_state_help_text}"
          focusable="true"
          aria-label="${domain.get_state_help_text}"
          role="tooltip"
        >
        <use aria-hidden="true" xlink:href="/public/img/sprite.svg#${iconType}"></use>
        </svg>
      </td>
      ${markupForSuborganizationRow}
      <td data-label="Action" class="width--action-column margin-bottom-3">
        <div class="tablet:display-flex tablet:flex-row flex-align-center margin-right-2">
          <a href="${actionUrl}">
            <svg class="usa-icon top-1px" aria-hidden="true" focusable="false" role="img" width="24">
              <use xlink:href="/public/img/sprite.svg#${domain.svg_icon}"></use>
            </svg>
            ${domain.action_label} <span class="usa-sr-only">${domain.name}</span>
          </a>
        </div>
      </td>
    `;
    tbody.appendChild(row);
  }
  initializeTooltips() {
    uswdsInitializeTooltips();
  }
}

// export function initDomainsTable() {
//   document.addEventListener('DOMContentLoaded', function() {
//     const isDomainsPage = document.getElementById("domains") 
//     if (isDomainsPage){
//       const domainsTable = new DomainsTable();
//       if (domainsTable.tableWrapper) {
//         // Initial load
//         domainsTable.loadTable(1);
//       }
//     }
//   });
// }

// For clicking the "Expiring" checkbox
document.addEventListener('DOMContentLoaded', () => {
  const expiringLink = document.getElementById('link-expiring-domains');

  if (expiringLink) {
      // Grab the selection for the status filter by
      const statusCheckboxes = document.querySelectorAll('input[name="filter-status"]');

      expiringLink.addEventListener('click', (event) => {
          event.preventDefault();
          // Loop through all statuses
          statusCheckboxes.forEach(checkbox => {  
            // To find the for checkbox for "Expiring soon"
            if (checkbox.value === "expiring") {
                // If the checkbox is not already checked, check it
                if (!checkbox.checked) {
                    checkbox.checked = true;
                    // Do the checkbox action
                    let event = new Event('change');
                    checkbox.dispatchEvent(event)  
                }
            }
          });
      });
  }
});