
import { BaseTable } from './table-base.js';

/**
 * EditMemberDomainsTable is used for PortfolioMember and PortfolioInvitedMember
 * Domain Editing.
 * 
 * This table has additional functionality for tracking and making changes
 * to domains assigned to the member/invited member.
 */
export class EditMemberDomainsTable extends BaseTable {
  
  constructor() {
    super('edit-member-domain');
    this.displayName = "domain";
    this.currentSortBy = 'name';
    this.initialDomainAssignments = []; // list of initially assigned domains
    this.initialDomainAssignmentsOnlyMember = []; // list of initially assigned domains
        // which are readonly
    this.addedDomains = []; // list of domains added to member
    this.removedDomains = []; // list of domains removed from member
    this.initializeDomainAssignments();
    this.initCancelEditDomainAssignmentButton();
  }
  getBaseUrl() {
    return document.getElementById("get_member_domains_json_url");
  }
  getDataObjects(data) {
    return data.domains;
  }
  /** getDomainAssignmentSearchParams is used to prepare search to populate
   * initialDomainAssignments and initialDomainAssignmentsOnlyMember
   * 
   * searches with memberOnly True so that only domains assigned to the member are returned
   */
  getDomainAssignmentSearchParams(portfolio) {
    let searchParams = new URLSearchParams();
    let emailValue = this.portfolioElement ? this.portfolioElement.getAttribute('data-email') : null;
    let memberIdValue = this.portfolioElement ? this.portfolioElement.getAttribute('data-member-id') : null;
    let memberOnly = true;
    if (portfolio)
      searchParams.append("portfolio", portfolio);
    if (emailValue)
      searchParams.append("email", emailValue);
    if (memberIdValue)
      searchParams.append("member_id", memberIdValue);
    if (memberOnly)
      searchParams.append("member_only", memberOnly);
    return searchParams;
  }
  /** getSearchParams extends base class getSearchParams.
   * 
   * additional searchParam for this table is checkedDomains. This is used to allow
   * for backend sorting by domains which are 'checked' in the form.
   */
  getSearchParams(page, sortBy, order, searchTerm, status, portfolio) {
    let searchParams = super.getSearchParams(page, sortBy, order, searchTerm, status, portfolio);
    // Add checkedDomains to searchParams
    // Clone the initial domains to avoid mutating them
    let checkedDomains = [...this.initialDomainAssignments];
    // Add IDs from addedDomains that are not already in checkedDomains
    this.addedDomains.forEach(domain => {
        if (!checkedDomains.includes(domain.id)) {
            checkedDomains.push(domain.id);
        }
    });
    // Remove IDs from removedDomains
    this.removedDomains.forEach(domain => {
        const index = checkedDomains.indexOf(domain.id);
        if (index !== -1) {
            checkedDomains.splice(index, 1);
        }
    });
    // Append updated checkedDomain IDs to searchParams
    if (checkedDomains.length > 0) {
        searchParams.append("checkedDomainIds", checkedDomains.join(","));
    }
    return searchParams;
  }
  addRow(dataObject, tbody, customTableOptions) {
    const domain = dataObject;
    const row = document.createElement('tr');
    // console.log("initialDomainAssignments: " + this.initialDomainAssignments);
    // console.log("testing domain: " + domain.id);
    // console.log(`this.addedDomains ${JSON.stringify(this.addedDomains)}`)
    // console.log(`this.removedDomains ${JSON.stringify(this.removedDomains)}`)
    let checked = false;
    let disabled = false;
    if (
      (this.initialDomainAssignments.includes(domain.id) || 
      this.addedDomains.map(obj => obj.id).includes(domain.id)) && 
      !this.removedDomains.map(obj => obj.id).includes(domain.id)
    ) {
      console.log("checked domain: " + domain.id);
      checked = true;
    }
    if (this.initialDomainAssignmentsOnlyMember.includes(domain.id)) {
      console.log("disabled domain: " + domain.id);
      disabled = true;
    }
    
    row.innerHTML = `
        <td data-label="Selection" data-sort-value="0" class="padding-right-105">
            <div class="usa-checkbox">
                <input
                    class="usa-checkbox__input"
                    id="${domain.id}"
                    type="checkbox"
                    name="${domain.name}"
                    value="${domain.id}"
                    ${checked ? 'checked' : ''}
                    ${disabled ? 'disabled' : ''}
                />
                <label class="usa-checkbox__label margin-top-0" for="${domain.id}">
                    <span class="sr-only">${domain.id}</span>
                </label>
            </div>
        </td>
        <td data-label="Domain name">
            ${domain.name}
            ${disabled ? '<span class="display-block margin-top-05 text-gray-50">Domains must have one domain manager. To unassign this member, the domain needs another domain manager.</span>' : ''}
        </td>
    `;
    tbody.appendChild(row);
  }
  /**
   * initializeDomainAssignments searches via ajax on page load for domains assigned to
   * member. It populates both initialDomainAssignments and initialDomainAssignmentsOnlyMember.
   * It is called once per page load, but not called with subsequent table changes.
   */
  initializeDomainAssignments() {
    const baseUrlValue = this.getBaseUrl()?.innerHTML ?? null;
    if (!baseUrlValue) return;
    let searchParams = this.getDomainAssignmentSearchParams(this.portfolioValue);
    let url = baseUrlValue + "?" + searchParams.toString();
    fetch(url)
    .then(response => response.json())
    .then(data => {
      if (data.error) {
        console.error('Error in AJAX call: ' + data.error);
        return;
      }

      let dataObjects = this.getDataObjects(data);
      console.log(dataObjects);
      // Map the id attributes of dataObjects to this.initialDomainAssignments
      this.initialDomainAssignments = dataObjects.map(obj => obj.id);
      this.initialDomainAssignmentsOnlyMember = dataObjects
        .filter(obj => obj.member_is_only_manager)
        .map(obj => obj.id);

      console.log(this.initialDomainAssignments);
    })
    .catch(error => console.error('Error fetching domain assignments:', error));
  }
  /**
   * Initializes listeners on checkboxes in the table. Checkbox listeners are used
   * in this case to track changes to domain assignments in js (addedDomains and removedDomains)
   * before changes are saved.
   * initCheckboxListeners is called each time table is loaded.
   */
  initCheckboxListeners() {
    const checkboxes = this.tableWrapper.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(checkbox => {
      checkbox.addEventListener('change', () => {
        const domain = { id: +checkbox.value, name: checkbox.name };

        if (checkbox.checked) {
            this.updateDomainLists(domain, this.removedDomains, this.addedDomains);
        } else {
            this.updateDomainLists(domain, this.addedDomains, this.removedDomains);
        }
      });
    });
  }
  /**
   * Helper function which updates domain lists. When called, if domain is in the fromList,
   * it removes it; if domain is not in the toList, it is added to the toList.
   * @param {*} domain - object containing the domain id and name
   * @param {*} fromList - list of domains
   * @param {*} toList - list of domains
   */
  updateDomainLists(domain, fromList, toList) {
    const index = fromList.findIndex(item => item.id === domain.id && item.name === domain.name);

    if (index > -1) {
      fromList.splice(index, 1); // Remove from the `fromList` if it exists
    } else {
      toList.push(domain); // Add to the `toList` if not already there
    }
  }
  /**
   * initializes the Cancel button on the Edit domains page.
   * Cancel triggers modal in certain conditions and the initialization for the modal is done
   * in this function.
   */
  initCancelEditDomainAssignmentButton() {
    const cancelEditDomainAssignmentButton = document.getElementById('cancel-edit-domain-assignments');
    if (!cancelEditDomainAssignmentButton) {
      console.error("Expected element #cancel-edit-domain-assignments, but it does not exist.");
      return; // Exit early if the button doesn't exist
    }

    // Find the last breadcrumb link
    const lastPageLinkElement = document.querySelector('.usa-breadcrumb__list-item:nth-last-child(2) a');
    const lastPageLink = lastPageLinkElement ? lastPageLinkElement.getAttribute('href') : null;

    const hiddenModalTrigger = document.getElementById("hidden-cancel-edit-domain-assignments-modal-trigger");

    if (!lastPageLink) {
      console.warn("Last breadcrumb link not found or missing href.");
    }
    if (!hiddenModalTrigger) {
      console.warn("Hidden modal trigger not found.");
    }

    // Add click event listener
    cancelEditDomainAssignmentButton.addEventListener('click', () => {
      console.log('click cancel')
      if (this.addedDomains.length || this.removedDomains.length) {
          console.log('Changes detected. Triggering modal...');
          hiddenModalTrigger.click();
      } else if (lastPageLink) {
          window.location.href = lastPageLink; // Redirect to the last breadcrumb link
      } else {
          console.warn("No changes detected, but no valid lastPageLink to navigate to.");
          
      }
    });
  }
    
}

export function initEditMemberDomainsTable() {
  document.addEventListener('DOMContentLoaded', function() {
      const isEditMemberDomainsPage = document.getElementById("edit-member-domains");
      if (isEditMemberDomainsPage) {
        console.log("isEditMemberDomainsPage");
        const editMemberDomainsTable = new EditMemberDomainsTable();
        if (editMemberDomainsTable.tableWrapper) {
          // Initial load
          editMemberDomainsTable.loadTable(1);
        }
      }
    });
}
