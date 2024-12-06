
import { BaseTable } from './table-base.js';

export class EditMemberDomainsTable extends BaseTable {

  constructor() {
    super('edit-member-domain');
    this.currentSortBy = 'name';
    this.initialDomainAssignments = [];
    this.initialDomainAssignmentsOnlyMember = [];
    this.addedDomains = [];
    this.removedDomains = [];
    this.initializeDomainAssignments();
  }
  getBaseUrl() {
    return document.getElementById("get_member_domains_edit_json_url");
  }
  getDataObjects(data) {
    return data.domains;
  }
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
  getSearchParams(page, sortBy, order, searchTerm, status, portfolio) {
    let searchParams = super.getSearchParams(page, sortBy, order, searchTerm, status, portfolio);
    if (this.addedDomains)
      searchParams.append("addedDomainIds", this.addedDomains);
    if (this.removedDomains)
      searchParams.append("removedDomainIds", this.removedDomains);
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
      this.addedDomains.map(obj => obj.id).includes(domain.id.toString())) && 
      !this.removedDomains.map(obj => obj.id).includes(domain.id.toString())
    ) {
      console.log("checked domain: " + domain.id);
      checked = true;
    }
    if (this.initialDomainAssignmentsOnlyMember.includes(domain.id)) {
      console.log("disabled domain: " + domain.id);
      disabled = true;
    }
    
    row.innerHTML = `
        <td data-label="Selection" data-sort-value="0">
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
                <label class="usa-checkbox__label" for="${domain.id}">
                    <span class="sr-only">${domain.id}</span>
                </label>
            </div>
        </td>
        <td data-label="Domain name">
            ${domain.name}
        </td>
    `;
    tbody.appendChild(row);
  }
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
  
    initCheckboxListeners() {
        const checkboxes = this.tableWrapper.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                const domain = { id: checkbox.value, name: checkbox.name };

                if (checkbox.checked) {
                    this.updateDomainLists(domain, this.removedDomains, this.addedDomains);
                } else {
                    this.updateDomainLists(domain, this.addedDomains, this.removedDomains);
                }

                // console.log(`this.addedDomains ${JSON.stringify(this.addedDomains)}`)
                // console.log(`this.removedDomains ${JSON.stringify(this.removedDomains)}`)
            });
        });
    }

    updateDomainLists(domain, fromList, toList) {
        const index = fromList.findIndex(item => item.id === domain.id && item.name === domain.name);

        if (index > -1) {
            fromList.splice(index, 1); // Remove from the `fromList` if it exists
        } else {
            toList.push(domain); // Add to the `toList` if not already there
        }
    }


}

export function initEditMemberDomainsTable() {
  document.addEventListener('DOMContentLoaded', function() {
      const isEditMemberDomainsPage = document.getElementById("edit-member-domains");
      if (isEditMemberDomainsPage){
        console.log("isEditMemberDomainsPage");
        const editMemberDomainsTable = new EditMemberDomainsTable();
        if (editMemberDomainsTable.tableWrapper) {
          // Initial load
          editMemberDomainsTable.loadTable(1);
        }
      }
    });
}
