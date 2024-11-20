import { hideElement, showElement, scrollToElement } from '../modules-common/helpers.js';

import { LoadTableBase } from './table-base.js';

export class MembersTable extends LoadTableBase {

  constructor() {
    super('members');
  }
  
  /**
   * Initializes "Show More" buttons on the page, enabling toggle functionality to show or hide content.
   * 
   * The function finds elements with "Show More" buttons and sets up a click event listener to toggle the visibility
   * of a corresponding content div. When clicked, the button updates its visual state (e.g., text/icon change),
   * and the associated content is shown or hidden based on its current visibility status.
   *
   * @function initShowMoreButtons
   */
  initShowMoreButtons() {
    /**
     * Toggles the visibility of a content section when the "Show More" button is clicked.
     * Updates the button text/icon based on whether the content is shown or hidden.
     *
     * @param {HTMLElement} toggleButton - The button that toggles the content visibility.
     * @param {HTMLElement} contentDiv - The content div whose visibility is toggled.
     * @param {HTMLElement} buttonParentRow - The parent row element containing the button.
     */
    function toggleShowMoreButton(toggleButton, contentDiv, buttonParentRow) {
      const spanElement = toggleButton.querySelector('span');
      const useElement = toggleButton.querySelector('use');
      if (contentDiv.classList.contains('display-none')) {
        showElement(contentDiv);
        spanElement.textContent = 'Close';
        useElement.setAttribute('xlink:href', '/public/img/sprite.svg#expand_less');
        buttonParentRow.classList.add('hide-td-borders');
        toggleButton.setAttribute('aria-label', 'Close additional information');
      } else {    
        hideElement(contentDiv);
        spanElement.textContent = 'Expand';
        useElement.setAttribute('xlink:href', '/public/img/sprite.svg#expand_more');
        buttonParentRow.classList.remove('hide-td-borders');
        toggleButton.setAttribute('aria-label', 'Expand for additional information');
      }
    }
  
    let toggleButtons = document.querySelectorAll('.usa-button--show-more-button');
    toggleButtons.forEach((toggleButton) => {
      
      // get contentDiv for element specified in data-for attribute of toggleButton
      let dataFor = toggleButton.dataset.for;
      let contentDiv = document.getElementById(dataFor);
      let buttonParentRow = toggleButton.parentElement.parentElement;
      if (contentDiv && contentDiv.tagName.toLowerCase() === 'tr' && contentDiv.classList.contains('show-more-content') && buttonParentRow && buttonParentRow.tagName.toLowerCase() === 'tr') {
        toggleButton.addEventListener('click', function() {
          toggleShowMoreButton(toggleButton, contentDiv, buttonParentRow);
        });
      } else {
        console.warn('Found a toggle button with no associated toggleable content or parent row');
      }

    });
  }

  /**
   * Converts a given `last_active` value into a display value and a numeric sort value.
   * The input can be a UTC date, the strings "Invited", "Invalid date", or null/undefined.
   * 
   * @param {string} last_active - UTC date string or special status like "Invited" or "Invalid date".
   * @returns {Object} - An object containing `display_value` (formatted date or status string) 
   *                     and `sort_value` (numeric value for sorting).
   */
  handleLastActive(last_active) {
    const invited = 'Invited';
    const invalid_date = 'Invalid date';
    const options = { year: 'numeric', month: 'long', day: 'numeric' }; // Date display format

    let display_value = invalid_date; // Default display value for invalid or null dates
    let sort_value = -1;              // Default sort value for invalid or null dates

    if (last_active === invited) {
      // Handle "Invited" status: special case with 0 sort value
      display_value = invited;
      sort_value = 0;
    } else if (last_active && last_active !== invalid_date) {
      // Parse and format valid UTC date strings
      const parsedDate = new Date(last_active);

      if (!isNaN(parsedDate.getTime())) {
        // Valid date
        display_value = parsedDate.toLocaleDateString('en-US', options);
        sort_value = parsedDate.getTime(); // Use timestamp for sorting
      } else {
        console.error(`Error: Invalid date string provided: ${last_active}`);
      }
    }

    return { display_value, sort_value };
  }

  /**
   * Generates HTML for the list of domains assigned to a member.
   * 
   * @param {number} num_domains - The number of domains the member is assigned to.
   * @param {Array} domain_names - An array of domain names.
   * @param {Array} domain_urls - An array of corresponding domain URLs.
   * @returns {string} - A string of HTML displaying the domains assigned to the member.
   */
  generateDomainsHTML(num_domains, domain_names, domain_urls, action_url) {
    // Initialize an empty string for the HTML
    let domainsHTML = '';

    // Only generate HTML if the member has one or more assigned domains
    if (num_domains > 0) {
      domainsHTML += "<div class='desktop:grid-col-5 margin-bottom-2 desktop:margin-bottom-0'>";
      domainsHTML += "<h4 class='margin-y-0 text-primary'>Domains assigned</h4>";
      domainsHTML += `<p class='margin-y-0'>This member is assigned to ${num_domains} domains:</p>`;
      domainsHTML += "<ul class='usa-list usa-list--unstyled margin-y-0'>";

      // Display up to 6 domains with their URLs
      for (let i = 0; i < num_domains && i < 6; i++) {
        domainsHTML += `<li><a href="${domain_urls[i]}">${domain_names[i]}</a></li>`;
      }

      domainsHTML += "</ul>";

      // If there are more than 6 domains, display a "View assigned domains" link
      if (num_domains >= 6) {
        domainsHTML += `<p><a href="${action_url}/domains">View assigned domains</a></p>`;
      }

      domainsHTML += "</div>";
    }

    return domainsHTML;
  }

  /**
   * Generates an HTML string summarizing a user's additional permissions within a portfolio, 
   * based on the user's permissions and predefined permission choices.
   *
   * @param {Array} member_permissions - An array of permission strings that the member has.
   * @param {Object} UserPortfolioPermissionChoices - An object containing predefined permission choice constants.
   *        Expected keys include:
   *        - VIEW_ALL_DOMAINS
   *        - VIEW_MANAGED_DOMAINS
   *        - EDIT_REQUESTS
   *        - VIEW_ALL_REQUESTS
   *        - EDIT_MEMBERS
   *        - VIEW_MEMBERS
   * 
   * @returns {string} - A string of HTML representing the user's additional permissions.
   *                     If the user has no specific permissions, it returns a default message
   *                     indicating no additional permissions.
   *
   * Behavior:
   * - The function checks the user's permissions (`member_permissions`) and generates
   *   corresponding HTML sections based on the permission choices defined in `UserPortfolioPermissionChoices`.
   * - Permissions are categorized into domains, requests, and members:
   *   - Domains: Determines whether the user can view or manage all or assigned domains.
   *   - Requests: Differentiates between users who can edit requests, view all requests, or have no request privileges.
   *   - Members: Distinguishes between members who can manage or only view other members.
   * - If no relevant permissions are found, the function returns a message stating that the user has no additional permissions.
   * - The resulting HTML always includes a header "Additional permissions for this member" and appends the relevant permission descriptions.
   */
  generatePermissionsHTML(member_permissions, UserPortfolioPermissionChoices) {
    let permissionsHTML = '';

    // Check domain-related permissions
    if (member_permissions.includes(UserPortfolioPermissionChoices.VIEW_ALL_DOMAINS)) {
      permissionsHTML += "<p class='margin-top-1 p--blockquote'><strong class='text-base-dark'>Domains:</strong> Can view all organization domains. Can manage domains they are assigned to and edit information about the domain (including DNS settings).</p>";
    } else if (member_permissions.includes(UserPortfolioPermissionChoices.VIEW_MANAGED_DOMAINS)) {
      permissionsHTML += "<p class='margin-top-1 p--blockquote'><strong class='text-base-dark'>Domains:</strong> Can manage domains they are assigned to and edit information about the domain (including DNS settings).</p>";
    }

    // Check request-related permissions
    if (member_permissions.includes(UserPortfolioPermissionChoices.EDIT_REQUESTS)) {
      permissionsHTML += "<p class='margin-top-1 p--blockquote'><strong class='text-base-dark'>Domain requests:</strong> Can view all organization domain requests. Can create domain requests and modify their own requests.</p>";
    } else if (member_permissions.includes(UserPortfolioPermissionChoices.VIEW_ALL_REQUESTS)) {
      permissionsHTML += "<p class='margin-top-1 p--blockquote'><strong class='text-base-dark'>Domain requests (view-only):</strong> Can view all organization domain requests. Can't create or modify any domain requests.</p>";
    }

    // Check member-related permissions
    if (member_permissions.includes(UserPortfolioPermissionChoices.EDIT_MEMBERS)) {
      permissionsHTML += "<p class='margin-top-1 p--blockquote'><strong class='text-base-dark'>Members:</strong> Can manage members including inviting new members, removing current members, and assigning domains to members.</p>";
    } else if (member_permissions.includes(UserPortfolioPermissionChoices.VIEW_MEMBERS)) {
      permissionsHTML += "<p class='margin-top-1 p--blockquote'><strong class='text-base-dark'>Members (view-only):</strong> Can view all organizational members. Can't manage any members.</p>";
    }

    // If no specific permissions are assigned, display a message indicating no additional permissions
    if (!permissionsHTML) {
      permissionsHTML += "<p class='margin-top-1 p--blockquote'><b>No additional permissions:</b> There are no additional permissions for this member.</p>";
    }

    // Add a permissions header and wrap the entire output in a container
    permissionsHTML = "<div class='desktop:grid-col-7'><h4 class='margin-y-0 text-primary'>Additional permissions for this member</h4>" + permissionsHTML + "</div>";
    
    return permissionsHTML;
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
          "search_term": searchTerm
        }
      );
      if (portfolio)
        searchParams.append("portfolio", portfolio)


      // --------- FETCH DATA
      // fetch json of page of domains, given params
      let baseUrl = document.getElementById("get_members_json_url");
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
          const memberList = document.querySelector('#members tbody');
          memberList.innerHTML = '';

          const UserPortfolioPermissionChoices = data.UserPortfolioPermissionChoices;
          const invited = 'Invited';
          const invalid_date = 'Invalid date';

          data.members.forEach(member => {
            const member_id = member.source + member.id;
            const member_name = member.name;
            const member_display = member.member_display;
            const member_permissions = member.permissions;
            const domain_urls = member.domain_urls;
            const domain_names = member.domain_names;
            const num_domains = domain_urls.length;
            
            const last_active = this.handleLastActive(member.last_active);

            const action_url = member.action_url;
            const action_label = member.action_label;
            const svg_icon = member.svg_icon;
      
            const row = document.createElement('tr');

            let admin_tagHTML = ``;
            if (member.is_admin)
              admin_tagHTML = `<span class="usa-tag margin-left-1 bg-primary">Admin</span>`

            // generate html blocks for domains and permissions for the member
            let domainsHTML = this.generateDomainsHTML(num_domains, domain_names, domain_urls, action_url);
            let permissionsHTML = this.generatePermissionsHTML(member_permissions, UserPortfolioPermissionChoices);
            
            // domainsHTML block and permissionsHTML block need to be wrapped with hide/show toggle, Expand
            let showMoreButton = '';
            const showMoreRow = document.createElement('tr');
            if (domainsHTML || permissionsHTML) {
              showMoreButton = `
                <button 
                  type="button" 
                  class="usa-button--show-more-button usa-button usa-button--unstyled display-block margin-top-1" 
                  data-for=${member_id}
                  aria-label="Expand for additional information"
                >
                  <span>Expand</span>
                  <svg class="usa-icon usa-icon--big" aria-hidden="true" focusable="false" role="img" width="24">
                    <use xlink:href="/public/img/sprite.svg#expand_more"></use>
                  </svg>
                </button>
              `;

              showMoreRow.innerHTML = `<td colspan='3' headers="header-member row-header-${member_id}" class="padding-top-0"><div class='grid-row'>${domainsHTML} ${permissionsHTML}</div></td>`;
              showMoreRow.classList.add('show-more-content');
              showMoreRow.classList.add('display-none');
              showMoreRow.id = member_id;
            }

            row.innerHTML = `
              <th role="rowheader" headers="header-member" data-label="member email" id='row-header-${member_id}'>
                ${member_display} ${admin_tagHTML} ${showMoreButton}
              </th>
              <td headers="header-last-active row-header-${member_id}" data-sort-value="${last_active.sort_value}" data-label="last_active">
                ${last_active.display_value}
              </td>
              <td headers="header-action row-header-${member_id}">
                <a href="${action_url}">
                  <svg class="usa-icon" aria-hidden="true" focusable="false" role="img" width="24">
                    <use xlink:href="/public/img/sprite.svg#${svg_icon}"></use>
                  </svg>
                  ${action_label} <span class="usa-sr-only">${member_name}</span>
                </a>
              </td>
            `;
            memberList.appendChild(row);
            if (domainsHTML || permissionsHTML) {
              memberList.appendChild(showMoreRow);
            }
          });

          this.initShowMoreButtons();

          // Do not scroll on first page load
          if (scroll)
            scrollToElement('class', 'members');
          this.scrollToTable = true;

          // update pagination
          this.updatePagination(
            'member',
            '#members-pagination',
            '#members-pagination .usa-pagination__counter',
            '#members',
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
      .catch(error => console.error('Error fetching members:', error));
  }
}

export function initMembersTable() {
  document.addEventListener('DOMContentLoaded', function() {
    const isMembersPage = document.getElementById("members") 
    if (isMembersPage){
      const membersTable = new MembersTable();
      if (membersTable.tableWrapper) {
        // Initial load
        membersTable.loadTable(1);
      }
    }
  });
}
