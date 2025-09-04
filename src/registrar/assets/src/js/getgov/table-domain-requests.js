import { hideElement, showElement, getCsrfToken, unsafeStripHtmlTags } from './helpers.js';
import { uswdsInitializeModals, uswdsUnloadModals } from './helpers-uswds.js';

import { BaseTable, addModal, generateKebabHTML } from './table-base.js';


const utcDateString = (dateString) => {
  const date = new Date(dateString);
  const utcYear = date.getUTCFullYear();
  const utcMonth = date.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' });
  const utcDay = date.getUTCDate().toString().padStart(2, '0');
  let utcHours = date.getUTCHours();
  const utcMinutes = date.getUTCMinutes().toString().padStart(2, '0');

  const ampm = utcHours >= 12 ? 'PM' : 'AM';
  utcHours = utcHours % 12 || 12;  // Convert to 12-hour format, '0' hours should be '12'

  return `${utcMonth} ${utcDay}, ${utcYear}, ${utcHours}:${utcMinutes} ${ampm} UTC`;
};


export class DomainRequestsTable extends BaseTable {

  constructor() {
    super('domain-request');
    this.displayName = "domain request";
    this.currentSortBy = 'last_submitted_date';
    this.currentOrder = 'desc';
  }

  getBaseUrl() {
    return document.getElementById("get_domain_requests_json_url");
  }
  
  toggleExportButton(requests) {
    const exportButton = document.getElementById('export-csv'); 
    if (exportButton) {
        if (requests.length > 0) {
            showElement(exportButton);
        } else {
            hideElement(exportButton);
        }
    }
  }

  getDataObjects(data) {
    return data.domain_requests;
  }
  unloadModals() {
    uswdsUnloadModals();
  }
  customizeTable(data) {

    // Manage "export as CSV" visibility for domain requests
    this.toggleExportButton(data.domain_requests);

    let isDeletable = data.domain_requests.some(request => request.is_deletable);
    return { 'hasAdditionalActions': isDeletable };
  }

  addRow(dataObject, tbody, customTableOptions) {
    const request = dataObject;
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    const domainName = request.requested_domain ? request.requested_domain : `New domain request <br><span class="text-base font-body-xs">(${utcDateString(request.created_at)})</span>`;
    const actionUrl = request.action_url;
    const actionLabel = request.action_label;
    const submissionDate = request.last_submitted_date ? new Date(request.last_submitted_date).toLocaleDateString('en-US', options) : `<span class="text-base">Not submitted</span>`;

    // The markup for the delete function either be a simple trigger or a 3 dots menu with a hidden trigger (in the case of portfolio requests page)
    // If the request is not deletable, use the following (hidden) span for ANDI screenreaders to indicate this state to the end user
    let modalTrigger =  `
    <span class="usa-sr-only">Domain request cannot be deleted now. Edit the request for more information.</span>`;

    let markupRequesterRow = '';
    

    if (this.portfolioValue) {
      markupRequesterRow = `
        <td data-label="Created by">
            <span class="text-wrap break-word">${request.requester ? request.requester : ''}</span>
        </td>
      `
    }

    if (request.is_deletable) {
      // 1st path (non-org): Just a modal trigger in any screen size for non-org users
      modalTrigger = `
        <a 
          role="button" 
          id="button-toggle-delete-domain-${request.id}"
          href="#toggle-delete-domain-${request.id}"
          class="usa-button text-secondary usa-button--unstyled text-no-underline late-loading-modal-trigger line-height-sans-5"
          aria-controls="toggle-delete-domain-${request.id}"
          data-open-modal
        >
          <svg class="usa-icon" aria-hidden="true" focusable="false" role="img" width="24">
            <use xlink:href="/public/img/sprite.svg#delete"></use>
          </svg> Delete <span class="usa-sr-only">${domainName}</span>
        </a>`

      // Request is deletable, modal and modalTrigger are built. Now check if we are on the portfolio requests page (by seeing if there is a portfolio value) and enhance the modalTrigger accordingly
      if (this.portfolioValue) {
        // NOTE: THIS IS NOT SUITABLE FOR SANITIZING DANGEROUS STRINGS
        const sanitizedDomainName = unsafeStripHtmlTags(domainName);
        // 2nd path (org model): Just a modal trigger on mobile for org users or kebab + accordion with nested modal trigger on desktop for org users
        modalTrigger = generateKebabHTML('delete-domain', request.id, 'Delete', sanitizedDomainName);
      }
    }

    const row = document.createElement('tr');
    row.innerHTML = `
      <th scope="row" role="rowheader" data-label="Domain name">
        ${domainName}
      </th>
      <td data-sort-value="${new Date(request.last_submitted_date).getTime()}" data-label="Date submitted">
        ${submissionDate}
      </td>
      ${markupRequesterRow}
      <td data-label="Status">
        ${request.status}
      </td>
      <td data-label="Action" class="width--action-column margin-bottom-3">
        <div class="tablet:display-flex tablet:flex-row">
          <a href="${actionUrl}" ${customTableOptions.hasAdditionalActions ? "class='margin-right-2'" : ''}>
            <svg class="usa-icon top-1px" aria-hidden="true" focusable="false" role="img" width="24">
              <use xlink:href="/public/img/sprite.svg#${request.svg_icon}"></use>
            </svg>
            ${actionLabel} <span class="usa-sr-only">${request.requested_domain ? request.requested_domain : 'New domain request'}</span>
          </a>
          ${customTableOptions.hasAdditionalActions ? modalTrigger : ''}
        </div>
      </td>
    `;
    tbody.appendChild(row);
    if (request.is_deletable) DomainRequestsTable.addDomainRequestsModal(request.requested_domain, request.id, request.created_at, tbody);
  }

  loadModals(page, total, unfiltered_total) {
    // initialize modals immediately after the DOM content is updated
    uswdsInitializeModals();

    // Now the DOM and modals are ready, add listeners to the submit buttons
    const modals = document.querySelectorAll('.usa-modal__content');

    modals.forEach(modal => {
      const submitButton = modal.querySelector('.usa-modal__submit');
      const closeButton = modal.querySelector('.usa-modal__close');
      submitButton.addEventListener('click', () => {
        let pk = submitButton.getAttribute('data-pk');
        // Workaround: Close the modal to remove the USWDS UI local classes
        closeButton.click();
        // If we're deleting the last item on a page that is not page 1, we'll need to refresh the display to the previous page
        let pageToDisplay = page;
        if (total == 1 && unfiltered_total > 1) {
          pageToDisplay--;
        }

        this.deleteDomainRequest(pk, pageToDisplay);
      });
    });
  }

  /**
   * Delete is actually a POST API that requires a csrf token. The token will be waiting for us in the template as a hidden input.
   * @param {*} domainRequestPk - the identifier for the request that we're deleting
   * @param {*} pageToDisplay - If we're deleting the last item on a page that is not page 1, we'll need to display the previous page
  */
  deleteDomainRequest(domainRequestPk, pageToDisplay) {
    // Use to debug uswds modal issues
    //console.log('deleteDomainRequest')
    
    // Get csrf token
    const csrfToken = getCsrfToken();
    // Create FormData object and append the CSRF token
    const formData = `csrfmiddlewaretoken=${encodeURIComponent(csrfToken)}&delete-domain-request=`;

    fetch(`/domain-request/${domainRequestPk}/delete`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': csrfToken,
      },
      body: formData
    })
    .then(response => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      // Update data and UI
      this.loadTable(pageToDisplay, this.currentSortBy, this.currentOrder, this.scrollToTable, this.currentStatus, this.currentSearchTerm);
    })
    .catch(error => console.error('Error fetching domain requests:', error));
  }

  /**
     * Modal that displays when deleting a domain request 
     * @param {string} requested_domain - The requested domain URL 
     * @param {string} id - The request's ID
     * @param {string}} created_at - When the request was created at
     * @param {HTMLElement} wrapper_element - The element to which the modal is appended
     */
  static addDomainRequestsModal(requested_domain, id, created_at, wrapper_element) {
    // If the request is deletable, create modal body and insert it. This is true for both requests and portfolio requests pages
    let modalHeading = '';
    let modalDescription = '';

    if (requested_domain) {
      modalHeading = `Are you sure you want to delete ${requested_domain}?`;
      modalDescription = 'This will remove the domain request from the .gov registrar. This action cannot be undone.';
    } else {
      if (created_at) {
        modalHeading = 'Are you sure you want to delete this domain request?';
        modalDescription = `This will remove the domain request (created ${utcDateString(created_at)}) from the .gov registrar. This action cannot be undone`;
      } else {
        modalHeading = 'Are you sure you want to delete New domain request?';
        modalDescription = 'This will remove the domain request from the .gov registrar. This action cannot be undone.';
      }
    }

    const modalSubmit = `
      <button type="button"
      class="usa-button usa-button--secondary usa-modal__submit"
      data-pk = ${id}
      name="delete-domain-request">Yes, delete request</button>
    `

    addModal(`toggle-delete-domain-${id}`, 'Are you sure you want to continue?', 'Domain will be removed', modalHeading, modalDescription, modalSubmit, wrapper_element, true);

  }
}

export function initDomainRequestsTable() { 
  document.addEventListener('DOMContentLoaded', function() {
    const domainRequestsSectionWrapper = document.getElementById('domain-requests');
    if (domainRequestsSectionWrapper) {
      const domainRequestsTable = new DomainRequestsTable();
      if (domainRequestsTable.tableWrapper) {
        domainRequestsTable.loadTable(1);
      }
    }

    document.addEventListener('focusin', function(event) {
      closeOpenAccordions(event);
    });
    
    document.addEventListener('click', function(event) {
      closeOpenAccordions(event);
    });

    function closeMoreActionMenu(accordionThatIsOpen) {
      if (accordionThatIsOpen.getAttribute("aria-expanded") === "true") {
        accordionThatIsOpen.click();
      }
    }

    function closeOpenAccordions(event) {
      const openAccordions = document.querySelectorAll('.usa-button--more-actions[aria-expanded="true"]');
      openAccordions.forEach((openAccordionButton) => {
        // Find the corresponding accordion
        const accordion = openAccordionButton.closest('.usa-accordion--more-actions');
        if (accordion && !accordion.contains(event.target)) {
          // Close the accordion if the click is outside
          closeMoreActionMenu(openAccordionButton);
        }
      });
    }
  });
}
