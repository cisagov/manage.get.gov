import { BaseTable } from './table-base.js';

export class DomainsTable extends BaseTable {

  constructor() {
    super('domain');
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
        <td>
            <span class="text-wrap" aria-label="${domain.suborganization ? suborganization : 'No suborganization'}">${suborganization}</span>
        </td>
      `
    }
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
          class="usa-icon usa-tooltip usa-tooltip--registrar text-middle margin-bottom-05 text-accent-cool no-click-outline-and-cursor-help" 
          data-position="top"
          title="${domain.get_state_help_text}"
          focusable="true"
          aria-label="${domain.get_state_help_text}"
          role="tooltip"
        >
          <use aria-hidden="true" xlink:href="/public/img/sprite.svg#info_outline"></use>
        </svg>
      </td>
      ${markupForSuborganizationRow}
      <td>
        <a href="${actionUrl}">
          <svg class="usa-icon" aria-hidden="true" focusable="false" role="img" width="24">
            <use xlink:href="/public/img/sprite.svg#${domain.svg_icon}"></use>
          </svg>
          ${domain.action_label} <span class="usa-sr-only">${domain.name}</span>
        </a>
      </td>
    `;
    tbody.appendChild(row);
  }
}

export function initDomainsTable() {
  document.addEventListener('DOMContentLoaded', function() {
    const isDomainsPage = document.getElementById("domains") 
    if (isDomainsPage){
      const domainsTable = new DomainsTable();
      if (domainsTable.tableWrapper) {
        // Initial load
        domainsTable.loadTable(1);
      }
    }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const expiringLink = document.getElementById('link-expiring-domains');

  if (expiringLink) {
      // Grab the selection for the status filter by
      const statusCheckboxes = document.querySelectorAll('input[name="filter-status"]');
      
      expiringLink.addEventListener('click', (event) => {
          event.preventDefault();

          console.log('Expiring domains link clicked');
          
          // Loop through all statuses for "EXPIRING" checkbox
          statusCheckboxes.forEach(checkbox => {
              // Check for expiring checkbox 
              if (checkbox.value === "expiring") {
                  console.log("Expiring checkbox found:", checkbox);
                  
                  // And if not checked, check it
                  if (!checkbox.checked) {
                      checkbox.checked = true;
                      // Followed from the radio button method below
                      // Can also do: checkbox.dispatchEvent(new Event('change'));

                      let event = new Event('change');
                      checkbox.dispatchEvent(event);
                      console.log("Expiring checkbox checked");
                  }
              }
          });
          // We're supposed to reload the table with the new filter but it's not working
          // const domainsTable = new DomainsTable();
          // loadTable(page, sortBy = this.currentSortBy, order = this.currentOrder, scroll = this.scrollToTable, status = this.currentStatus, searchTerm =this.currentSearchTerm, portfolio = this.portfolioValue)
          // This is what others have -- domainsTable.loadTable(1, 'id', 'asc');
          // Maybe we can use something with status = this.currentStatus?
          // this.loadTable();
          // Maybe we don't need to load the table?
          console.log('Table filtered with expiring domains');
      });
  }
});


