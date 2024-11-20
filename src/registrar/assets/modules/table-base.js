import { hideElement, showElement, toggleCaret } from '../modules-common/helpers.js';

export class LoadTableBase {
  constructor(sectionSelector) {
    this.tableWrapper = document.getElementById(`${sectionSelector}__table-wrapper`);
    this.tableHeaders = document.querySelectorAll(`#${sectionSelector} th[data-sortable]`);
    this.currentSortBy = 'id';
    this.currentOrder = 'asc';
    this.currentStatus = [];
    this.currentSearchTerm = '';
    this.scrollToTable = false;
    this.searchInput = document.getElementById(`${sectionSelector}__search-field`);
    this.searchSubmit = document.getElementById(`${sectionSelector}__search-field-submit`);
    this.tableAnnouncementRegion = document.getElementById(`${sectionSelector}__usa-table__announcement-region`);
    this.resetSearchButton = document.getElementById(`${sectionSelector}__reset-search`);
    this.resetFiltersButton = document.getElementById(`${sectionSelector}__reset-filters`);
    this.statusCheckboxes = document.querySelectorAll(`.${sectionSelector} input[name="filter-status"]`);
    this.statusIndicator = document.getElementById(`${sectionSelector}__filter-indicator`);
    this.statusToggle = document.getElementById(`${sectionSelector}__usa-button--filter`);
    this.noTableWrapper = document.getElementById(`${sectionSelector}__no-data`);
    this.noSearchResultsWrapper = document.getElementById(`${sectionSelector}__no-search-results`);
    this.portfolioElement = document.getElementById('portfolio-js-value');
    this.portfolioValue = this.portfolioElement ? this.portfolioElement.getAttribute('data-portfolio') : null;
    this.initializeTableHeaders();
    this.initializeSearchHandler();
    this.initializeStatusToggleHandler();
    this.initializeFilterCheckboxes();
    this.initializeResetSearchButton();
    this.initializeResetFiltersButton();
    this.initializeAccordionAccessibilityListeners();
  }

  /**
 * Generalized function to update pagination for a list.
 * @param {string} itemName - The name displayed in the counter
 * @param {string} paginationSelector - CSS selector for the pagination container.
 * @param {string} counterSelector - CSS selector for the pagination counter.
 * @param {string} tableSelector - CSS selector for the header element to anchor the links to.
 * @param {number} currentPage - The current page number (starting with 1).
 * @param {number} numPages - The total number of pages.
 * @param {boolean} hasPrevious - Whether there is a page before the current page.
 * @param {boolean} hasNext - Whether there is a page after the current page.
 * @param {number} total - The total number of items.
 */  
  updatePagination(
    itemName,
    paginationSelector,
    counterSelector,
    parentTableSelector,
    currentPage,
    numPages,
    hasPrevious,
    hasNext,
    totalItems,
  ) {
    const paginationButtons = document.querySelector(`${paginationSelector} .usa-pagination__list`);
    const counterSelectorEl = document.querySelector(counterSelector);
    const paginationSelectorEl = document.querySelector(paginationSelector);
    counterSelectorEl.innerHTML = '';
    paginationButtons.innerHTML = '';

    // Buttons should only be displayed if there are more than one pages of results
    paginationButtons.classList.toggle('display-none', numPages <= 1);

    // Counter should only be displayed if there is more than 1 item
    paginationSelectorEl.classList.toggle('display-none', totalItems < 1);

    counterSelectorEl.innerHTML = `${totalItems} ${itemName}${totalItems > 1 ? 's' : ''}${this.currentSearchTerm ? ' for ' + '"' + this.currentSearchTerm + '"' : ''}`;

    if (hasPrevious) {
      const prevPageItem = document.createElement('li');
      prevPageItem.className = 'usa-pagination__item usa-pagination__arrow';
      prevPageItem.innerHTML = `
        <a href="${parentTableSelector}" class="usa-pagination__link usa-pagination__previous-page" aria-label="Previous page">
          <svg class="usa-icon" aria-hidden="true" role="img">
            <use xlink:href="/public/img/sprite.svg#navigate_before"></use>
          </svg>
          <span class="usa-pagination__link-text">Previous</span>
        </a>
      `;
      prevPageItem.querySelector('a').addEventListener('click', (event) => {
        event.preventDefault();
        this.loadTable(currentPage - 1);
      });
      paginationButtons.appendChild(prevPageItem);
    }

    // Add first page and ellipsis if necessary
    if (currentPage > 2) {
      paginationButtons.appendChild(this.createPageItem(1, parentTableSelector, currentPage));
      if (currentPage > 3) {
        const ellipsis = document.createElement('li');
        ellipsis.className = 'usa-pagination__item usa-pagination__overflow';
        ellipsis.setAttribute('aria-label', 'ellipsis indicating non-visible pages');
        ellipsis.innerHTML = '<span>…</span>';
        paginationButtons.appendChild(ellipsis);
      }
    }

    // Add pages around the current page
    for (let i = Math.max(1, currentPage - 1); i <= Math.min(numPages, currentPage + 1); i++) {
      paginationButtons.appendChild(this.createPageItem(i, parentTableSelector, currentPage));
    }

    // Add last page and ellipsis if necessary
    if (currentPage < numPages - 1) {
      if (currentPage < numPages - 2) {
        const ellipsis = document.createElement('li');
        ellipsis.className = 'usa-pagination__item usa-pagination__overflow';
        ellipsis.setAttribute('aria-label', 'ellipsis indicating non-visible pages');
        ellipsis.innerHTML = '<span>…</span>';
        paginationButtons.appendChild(ellipsis);
      }
      paginationButtons.appendChild(this.createPageItem(numPages, parentTableSelector, currentPage));
    }

    if (hasNext) {
      const nextPageItem = document.createElement('li');
      nextPageItem.className = 'usa-pagination__item usa-pagination__arrow';
      nextPageItem.innerHTML = `
        <a href="${parentTableSelector}" class="usa-pagination__link usa-pagination__next-page" aria-label="Next page">
          <span class="usa-pagination__link-text">Next</span>
          <svg class="usa-icon" aria-hidden="true" role="img">
            <use xlink:href="/public/img/sprite.svg#navigate_next"></use>
          </svg>
        </a>
      `;
      nextPageItem.querySelector('a').addEventListener('click', (event) => {
        event.preventDefault();
        this.loadTable(currentPage + 1);
      });
      paginationButtons.appendChild(nextPageItem);
    }
  }

  /**
   * A helper that toggles content/ no content/ no search results
   *
  */
  updateDisplay = (data, dataWrapper, noDataWrapper, noSearchResultsWrapper) => {
    const { unfiltered_total, total } = data;
    if (unfiltered_total) {
      if (total) {
        showElement(dataWrapper);
        hideElement(noSearchResultsWrapper);
        hideElement(noDataWrapper);
      } else {
        hideElement(dataWrapper);
        showElement(noSearchResultsWrapper);
        hideElement(noDataWrapper);
      }
    } else {
      hideElement(dataWrapper);
      hideElement(noSearchResultsWrapper);
      showElement(noDataWrapper);
    }
  };

  // Helper function to create a page item
  createPageItem(page, parentTableSelector, currentPage) {
    const pageItem = document.createElement('li');
    pageItem.className = 'usa-pagination__item usa-pagination__page-no';
    pageItem.innerHTML = `
      <a href="${parentTableSelector}" class="usa-pagination__button" aria-label="Page ${page}">${page}</a>
    `;
    if (page === currentPage) {
      pageItem.querySelector('a').classList.add('usa-current');
      pageItem.querySelector('a').setAttribute('aria-current', 'page');
    }
    pageItem.querySelector('a').addEventListener('click', (event) => {
      event.preventDefault();
      this.loadTable(page);
    });
    return pageItem;
  }

  /**
   * A helper that resets sortable table headers
   *
  */
  unsetHeader = (header) => {
    header.removeAttribute('aria-sort');
    let headerName = header.innerText;
    const headerLabel = `${headerName}, sortable column, currently unsorted"`;
    const headerButtonLabel = `Click to sort by ascending order.`;
    header.setAttribute("aria-label", headerLabel);
    header.querySelector('.usa-table__header__button').setAttribute("title", headerButtonLabel);
  };

  // Abstract method (to be implemented in the child class)
  loadTable(page, sortBy, order) {
    throw new Error('loadData() must be implemented in a subclass');
  }

  // Add event listeners to table headers for sorting
  initializeTableHeaders() {
    this.tableHeaders.forEach(header => {
      header.addEventListener('click', () => {
        const sortBy = header.getAttribute('data-sortable');
        let order = 'asc';
        // sort order will be ascending, unless the currently sorted column is ascending, and the user
        // is selecting the same column to sort in descending order
        if (sortBy === this.currentSortBy) {
          order = this.currentOrder === 'asc' ? 'desc' : 'asc';
        }
        // load the results with the updated sort
        this.loadTable(1, sortBy, order);
      });
    });
  }

  initializeSearchHandler() {
    this.searchSubmit.addEventListener('click', (e) => {
      e.preventDefault();
      this.currentSearchTerm = this.searchInput.value;
      // If the search is blank, we match the resetSearch functionality
      if (this.currentSearchTerm) {
        showElement(this.resetSearchButton);
      } else {
        hideElement(this.resetSearchButton);
      }
      this.loadTable(1, 'id', 'asc');
      this.resetHeaders();
    });
  }

  initializeStatusToggleHandler() {
    if (this.statusToggle) {
      this.statusToggle.addEventListener('click', () => {
        toggleCaret(this.statusToggle);
      });
    }
  }

  // Add event listeners to status filter checkboxes
  initializeFilterCheckboxes() {
    this.statusCheckboxes.forEach(checkbox => {
      checkbox.addEventListener('change', () => {
        const checkboxValue = checkbox.value;
        
        // Update currentStatus array based on checkbox state
        if (checkbox.checked) {
          this.currentStatus.push(checkboxValue);
        } else {
          const index = this.currentStatus.indexOf(checkboxValue);
          if (index > -1) {
            this.currentStatus.splice(index, 1);
          }
        }

        // Manage visibility of reset filters button
        if (this.currentStatus.length == 0) {
          hideElement(this.resetFiltersButton);
        } else {
          showElement(this.resetFiltersButton);
        }

        // Disable the auto scroll
        this.scrollToTable = false;

        // Call loadTable with updated status
        this.loadTable(1, 'id', 'asc');
        this.resetHeaders();
        this.updateStatusIndicator();
      });
    });
  }

  // Reset UI and accessibility
  resetHeaders() {
    this.tableHeaders.forEach(header => {
      // Unset sort UI in headers
      this.unsetHeader(header);
    });
    // Reset the announcement region
    this.tableAnnouncementRegion.innerHTML = '';
  }

  resetSearch() {
    this.searchInput.value = '';
    this.currentSearchTerm = '';
    hideElement(this.resetSearchButton);
    this.loadTable(1, 'id', 'asc');
    this.resetHeaders();
  }

  initializeResetSearchButton() {
    if (this.resetSearchButton) {
      this.resetSearchButton.addEventListener('click', () => {
        this.resetSearch();
      });
    }
  }

  resetFilters() {
    this.currentStatus = [];
    this.statusCheckboxes.forEach(checkbox => {
      checkbox.checked = false; 
    });
    hideElement(this.resetFiltersButton);

    // Disable the auto scroll
    this.scrollToTable = false;

    this.loadTable(1, 'id', 'asc');
    this.resetHeaders();
    this.updateStatusIndicator();
    // No need to toggle close the filters. The focus shift will trigger that for us.
  }

  initializeResetFiltersButton() {
    if (this.resetFiltersButton) {
      this.resetFiltersButton.addEventListener('click', () => {
        this.resetFilters();
      });
    }
  }

  updateStatusIndicator() {
    this.statusIndicator.innerHTML = '';
    // Even if the element is empty, it'll mess up the flex layout unless we set display none
    hideElement(this.statusIndicator);
    if (this.currentStatus.length)
      this.statusIndicator.innerHTML = '(' + this.currentStatus.length + ')';
      showElement(this.statusIndicator);
  }

  closeFilters() {
    if (this.statusToggle.getAttribute("aria-expanded") === "true") {
      this.statusToggle.click();
    }
  }

  initializeAccordionAccessibilityListeners() {
    // Instead of managing the toggle/close on the filter buttons in all edge cases (user clicks on search, user clicks on ANOTHER filter,
    // user clicks on main nav...) we add a listener and close the filters whenever the focus shifts out of the dropdown menu/filter button.
    // NOTE: We may need to evolve this as we add more filters.
    document.addEventListener('focusin', (event) => {
      const accordion = document.querySelector('.usa-accordion--select');
      const accordionThatIsOpen = document.querySelector('.usa-button--filter[aria-expanded="true"]');
      
      if (accordionThatIsOpen && !accordion.contains(event.target)) {
        this.closeFilters();
      }
    });

    // Close when user clicks outside
    // NOTE: We may need to evolve this as we add more filters.
    document.addEventListener('click', (event) => {
      const accordion = document.querySelector('.usa-accordion--select');
      const accordionThatIsOpen = document.querySelector('.usa-button--filter[aria-expanded="true"]');
    
      if (accordionThatIsOpen && !accordion.contains(event.target)) {
        this.closeFilters();
      }
    });
  }
}
