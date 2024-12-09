
import { BaseTable } from './table-base.js';

export class MemberDomainsTable extends BaseTable {

  constructor() {
    super('member-domain');
    this.displayName = "domain";
    this.currentSortBy = 'name';
  }
  getBaseUrl() {
    return document.getElementById("get_member_domains_json_url");
  }
  getDataObjects(data) {
    return data.domains;
  }
  addRow(dataObject, tbody, customTableOptions) {
    const domain = dataObject;
    const row = document.createElement('tr');
    row.innerHTML = `
      <td scope="row" data-label="Domain name">
        ${domain.name}
      </td>
    `;
    tbody.appendChild(row);
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
