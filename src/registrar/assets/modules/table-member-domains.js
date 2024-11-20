import { hideElement, showElement, scrollToElement, toggleCaret } from '../modules-common/helpers.js';
import { initializeTooltips, initializeModals, unloadModals } from './helpers-uswds.js';
import { getCsrfToken } from './helpers-csrf-token.js';

import { LoadTableBase } from './table-base.js';

export class MemberDomainsTable extends LoadTableBase {

  constructor() {
    super('member-domains');
    this.currentSortBy = 'name';
  }
  /**
   * Loads rows in the members list, as well as updates pagination around the members list
   * based on the supplied attributes.
   * @param {*} page - the page number of the results (starts with 1)
   * @param {*} sortBy - the sort column option
   * @param {*} order - the sort order {asc, desc}
   * @param {*} scroll - control for the scrollToElement functionality
   * @param {*} searchTerm - the search term
   * @param {*} portfolio - the portfolio id
   */
  loadTable(page, sortBy = this.currentSortBy, order = this.currentOrder, scroll = this.scrollToTable, searchTerm =this.currentSearchTerm, portfolio = this.portfolioValue) {

    // --------- SEARCH
    let searchParams = new URLSearchParams(
      {
        "page": page,
        "sort_by": sortBy,
        "order": order,
        "search_term": searchTerm,
      }
    );

    let emailValue = this.portfolioElement ? this.portfolioElement.getAttribute('data-email') : null;
    let memberIdValue = this.portfolioElement ? this.portfolioElement.getAttribute('data-member-id') : null;
    let memberOnly = this.portfolioElement ? this.portfolioElement.getAttribute('data-member-only') : null;

    if (portfolio)
      searchParams.append("portfolio", portfolio)
    if (emailValue)
      searchParams.append("email", emailValue)
    if (memberIdValue)
      searchParams.append("member_id", memberIdValue)
    if (memberOnly)
      searchParams.append("member_only", memberOnly)


    // --------- FETCH DATA
    // fetch json of page of domais, given params
    let baseUrl = document.getElementById("get_member_domains_json_url");
    if (!baseUrl) {
      return;
    }

    let baseUrlValue = baseUrl.innerHTML;
    if (!baseUrlValue) {
      return;
    }

    let url = `${baseUrlValue}?${searchParams.toString()}` //TODO: uncomment for search function
    fetch(url)
      .then(response => response.json())
      .then(data => {
        if (data.error) {
          console.error('Error in AJAX call: ' + data.error);
          return;
        }

        // handle the display of proper messaging in the event that no members exist in the list or search returns no results
        this.updateDisplay(data, this.tableWrapper, this.noTableWrapper, this.noSearchResultsWrapper, this.currentSearchTerm);

        // identify the DOM element where the domain list will be inserted into the DOM
        const memberDomainsList = document.querySelector('#member-domains tbody');
        memberDomainsList.innerHTML = '';


        data.domains.forEach(domain => {
          const row = document.createElement('tr');

          row.innerHTML = `
            <td scope="row" data-label="Domain name">
              ${domain.name}
            </td>
          `;
          memberDomainsList.appendChild(row);
        });

        // Do not scroll on first page load
        if (scroll)
          scrollToElement('class', 'member-domains');
        this.scrollToTable = true;

        // update pagination
        this.updatePagination(
          'member domain',
          '#member-domains-pagination',
          '#member-domains-pagination .usa-pagination__counter',
          '#member-domains',
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
  
export function initMemberDomainsTable() {
  document.addEventListener('DOMContentLoaded', function() {
      const isMemberDomainsPage = document.getElementById("member-domains") 
      if (isMemberDomainsPage){
        const memberDomainsTable = new MemberDomainsTable();
        if (memberDomainsTable.tableWrapper) {
          // Initial load
          memberDomainsTable.loadTable(1);
        }
      }
    });
}
