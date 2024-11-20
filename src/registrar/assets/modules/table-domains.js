import { scrollToElement } from '../modules-common/helpers.js';
import { initializeTooltips } from './helpers-uswds.js';

import { LoadTableBase } from './table-base.js';

export class DomainsTable extends LoadTableBase {

  constructor() {
    super('domains');
  }
  /**
   * Loads rows in the domains list, as well as updates pagination around the domains list
   * based on the supplied attributes.
   * @param {*} page - the page number of the results (starts with 1)
   * @param {*} sortBy - the sort column option
   * @param {*} order - the sort order {asc, desc}
   * @param {*} scroll - control for the scrollToElement functionality
   * @param {*} status - control for the status filter
   * @param {*} searchTerm - the search term
   * @param {*} portfolio - the portfolio id
   */
  loadTable(page, sortBy = this.currentSortBy, order = this.currentOrder, scroll = this.scrollToTable, status = this.currentStatus, searchTerm =this.currentSearchTerm, portfolio = this.portfolioValue) {

    // fetch json of page of domais, given params
    let baseUrl = document.getElementById("get_domains_json_url");
    if (!baseUrl) {
      return;
    }

    let baseUrlValue = baseUrl.innerHTML;
    if (!baseUrlValue) {
      return;
    }

    // fetch json of page of domains, given params
    let searchParams = new URLSearchParams(
      {
        "page": page,
        "sort_by": sortBy,
        "order": order,
        "status": status,
        "search_term": searchTerm
      }
    );
    if (portfolio)
      searchParams.append("portfolio", portfolio)

    let url = `${baseUrlValue}?${searchParams.toString()}`
    fetch(url)
      .then(response => response.json())
      .then(data => {
        if (data.error) {
          console.error('Error in AJAX call: ' + data.error);
          return;
        }

        // handle the display of proper messaging in the event that no domains exist in the list or search returns no results
        this.updateDisplay(data, this.tableWrapper, this.noTableWrapper, this.noSearchResultsWrapper, this.currentSearchTerm);

        // identify the DOM element where the domain list will be inserted into the DOM
        const domainList = document.querySelector('#domains tbody');
        domainList.innerHTML = '';

        data.domains.forEach(domain => {
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
          domainList.appendChild(row);
        });
        // initialize tool tips immediately after the associated DOM elements are added
        initializeTooltips();

        // Do not scroll on first page load
        if (scroll)
          scrollToElement('class', 'domains');
        this.scrollToTable = true;

        // update pagination
        this.updatePagination(
          'domain',
          '#domains-pagination',
          '#domains-pagination .usa-pagination__counter',
          '#domains',
          data.page,
          data.num_pages,
          data.has_previous,
          data.has_next,
          data.total,
        );
        this.currentSortBy = sortBy;
        this.currentOrder = order;
        this.currentSearchTerm = searchTerm;
      })
      .catch(error => console.error('Error fetching domains:', error));
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
