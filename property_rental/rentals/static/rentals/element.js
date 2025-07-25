document.addEventListener('DOMContentLoaded', function() {

    // Get the current URL path
    const path = window.location.pathname;
        
    // Extract the type from the path
    const match = path.match(/^\/(properties|tenants|transactions)\/?/);
    let type = match ? match[1] : null;
    console.log(type)

    // Convert plural form to singular
    if (type) {
        if (type === 'properties') {
            type = 'property';
        } else {
            type = type.slice(0, -1);
        }
    }

    // Hide details container
    document.getElementById(`${type}DetailsContainer`).style.display = 'none';

    // By default, load the corresponding table
    load_table(type);

    // Add event listener to the "New [Type]" button
    const newTypeButton = document.querySelector('.new-entry-button');
    newTypeButton.addEventListener('click', elementActionClickHandler);



    // Hide property selector for the chart (shown on the home page only)
    const propertySelector = document.getElementById('chartPropertySelection');
    if (propertySelector) {
        propertySelector.parentElement.style.display = 'none';
    }

    // Disable property valuation Edit form Edit and Delete button
    const propertyValuationEditDeleteButtons = document.getElementById("propertyEditValuationModalDiv");
    if (propertyValuationEditDeleteButtons) {
        disableEditDeleteButtons();
    }

    // Add event listener to the confirmation button to delete property valuation 
    const propertyValuationDeleteButton = document.getElementById("confirmPropertyValuationDeleteButton");
    if (propertyValuationDeleteButton) {
        propertyValuationDeleteButton.addEventListener("click", propertyValuationDeleteElementHandler);
    }

});

function load_table(type) {

    console.log(`loading table ${type}`)

    const Type = type.charAt(0).toUpperCase() + type.slice(1);

    if (type != "propertyValuation") {
        // Show the [type] table and hide other views
        document.getElementById(`${type}Table`).style.display = '';
        document.querySelector('.new-entry-button').style.display = '';
        document.getElementById(`${type}DetailsContainer`).style.display = 'none';
    }
    
    // Delete event listeners from the buttons on detailed [Type] page
    const detailElementCheck = document.getElementById(`back-to-${type}-table`);
    if (detailElementCheck) {
        // document.getElementById('confirmDeleteButton').removeEventListener('click', deleteElementHandler);
        document.getElementById(`back-to-${type}-table`).removeEventListener('click', backToTableClickHandler);
        document.getElementById(`edit${Type}Button`).removeEventListener('click', elementActionClickHandler);
        
        // const valuationButton = document.getElementById('valuationPropertyButton');
        // if (valuationButton) {
        //     valuationButton.removeEventListener('click', valuationButtonClickHandler);
        // }
        detailElementCheck.parentElement.remove();
    } else if (type === 'transaction' || type === 'propertyValuation') {
        // Remove event listeners for other types
        // document.getElementById('confirmDeleteButton').removeEventListener('click', deleteElementHandler);
        document.getElementById(`edit${Type}Button`).removeEventListener('click', elementActionClickHandler);

        // Assign transaction related event listeners for editing and deleting elements
        // document.getElementById('confirmDeleteButton').addEventListener('click', deleteElementHandler);
        document.getElementById(`edit${Type}Button`).addEventListener('click', elementActionClickHandler);
    }
    
    if (type != "propertyValuation") {
        // Show the page name
        document.querySelector('h2').innerHTML = (type === 'property') ? 'Properties' : `${Type}s`;
    }

    fetchTableData(type);
}

function fetchTableData(type) {

    let fetchUrl;

    if (type === 'propertyValuation') {
        const propertyId = document.getElementById(`deletePropertyButton`).getAttribute(`data-property-id`);
        fetchUrl = `/table-data/${type}?property_id=${propertyId}`;
    } else {
        fetchUrl = `/table-data/${type}`;
    }

    fetch(fetchUrl)
    .then(response => response.json())
    .then(data => {
        const tbody = document.querySelector(`#${type}Table tbody`);
        tbody.innerHTML = '';  // Clear the table body

        document.getElementById('datePicker').value = data[0];

        // Need to skip the first element as effective date is passed
        let isFirstElement = true;

        data.forEach(element => {

            if (isFirstElement) {
                isFirstElement = false; // Skip the first element
                return; // Skip processing this element
            }
            
            const row = document.createElement('tr');
            row.className = `${type}Row`;
            row.setAttribute(`data-${type}-id`, element.id);

            row.innerHTML = fillRow(type, element);

            tbody.appendChild(row);

            // Need to remove event listeners if already created to prevent duplication. Does not relate to transactions as there is no detailed page for transactions
            if (type != 'transaction' && type != 'propertyValuation') {
                const rowName = row.querySelector(`.${type}Name`);
                rowName.removeEventListener('click', tableElementClickHandler);
                rowName.addEventListener('click', tableElementClickHandler);
            }

        });

        if (type === 'transaction' || type === 'propertyValuation') {
            addTransactionValuationListeners(type);
        }
        
        // Add event listeners for vacate buttons
        if (type === 'tenant') {
            addVacateButtonListeners();
        }

        // Initialize or reinitialize DataTables
        if ($.fn.DataTable.isDataTable(`#${type}Table`)) {
            $(`#${type}Table`).DataTable().destroy();
        }
        
        // Configure column-specific settings
        let columnDefs = [
            { orderable: false, targets: '_all' } // Disable sorting on all columns by default
        ];
        
        // For tenant table, disable sorting on Action column and enable for others
        if (type === 'tenant') {
            columnDefs = [
                { orderable: true, targets: [0, 1, 2, 3, 4, 5, 6, 7] }, // Enable sorting for most columns
                { orderable: false, targets: [8] } // Disable sorting for Action column
            ];
        }
        
        $(`#${type}Table`).DataTable({
            searching: true,
            paging: true,
            pageLength: 10,
            lengthMenu: [[10, 25, 50, -1], [10, 25, 50, "All"]],
            order: [],
            columnDefs: columnDefs,
            // Bootstrap styling
            dom: '<"row"<"col-sm-12 col-md-6"l><"col-sm-12 col-md-6"f>>' +
                 '<"row"<"col-sm-12"tr>>' +
                 '<"row"<"col-sm-12 col-md-5"i><"col-sm-12 col-md-7"p>>',
            language: {
                search: "_INPUT_",
                searchPlaceholder: "Search records"
            }
        });
    })
    .catch(error => {
        console.error('Error fetching property data', error);
    });
}

// Compiling the row of the table of elements
function fillRow(type, element) {

    switch(type) {
        case 'property':
            // Determine the circle class based on property.status
            const circleClass = element.status === 'Rented out' ? 'green-circle' : 'red-circle';

            return `
                <td class="propertyName"><a href="">${element.name}</a></td>
                <td class="text-center">${element.location}</td>
                <td class="text-center">${formatDateToDdmmyy(element.rent_since)}</td>
                <td class="text-center"><i class="fas fa-circle ${circleClass}"></i></td>
                <td class="text-center">${formatNumberWithParentheses(element.currency, element.income_all_time)}</td>
                <td class="text-center">${formatNumberWithParentheses(element.currency, element.expense_all_time)}</td>
                <td class="text-center">${formatNumberWithParentheses(element.currency, element.net_income_all_time)}</td>
                <td></td>
                <td class="text-center">${formatNumberWithParentheses(element.currency, element.income_ytd)}</td>
                <td class="text-center">${formatNumberWithParentheses(element.currency, element.expense_ytd)}</td>
                <td class="text-center">${formatNumberWithParentheses(element.currency, element.net_income_ytd)}</td>
            `;
        case 'tenant':
            const currentRent = (element.lease_rent === 'No rent history for the Tenant') ? "–" : formatNumberWithParentheses(element.lease_native_currency, element.lease_rent);
            
            // Determine status display
            let statusDisplay = '';
            let statusClass = '';
            if (element.status === 'Active') {
                statusDisplay = '<i class="fas fa-circle text-success"></i> Active';
                statusClass = 'text-success';
            } else if (element.status === 'Will Vacate') {
                statusDisplay = '<i class="fas fa-circle text-warning"></i> Will Vacate';
                statusClass = 'text-warning';
            } else if (element.status === 'Vacated') {
                statusDisplay = '<i class="fas fa-circle text-danger"></i> Vacated';
                statusClass = 'text-danger';
            }
            
            // Determine action column content
            let actionColumn = '';
            if (element.status === 'Active') {
                actionColumn = `<button class="btn btn-sm btn-warning vacate-btn" data-tenant-id="${element.id}" data-tenant-name="${element.first_name}">Vacate</button>`;
            } else if (element.status === 'Will Vacate' && element.lease_end) {
                actionColumn = `<small class="text-muted">Vacates: ${formatDateToDdmmyy(element.lease_end)}</small>`;
            } else if (element.status === 'Vacated' && element.lease_end) {
                actionColumn = `<small class="text-muted">Vacated: ${formatDateToDdmmyy(element.lease_end)}</small>`;
            }
            
            return `
                <td class="tenantName"><a href="">${element.first_name}</a></td>
                <td class="text-center">${element.property}</td>
                <td class="text-center">${formatDateToDdmmyy(element.lease_start)}</td>
                <td class="text-center ${statusClass}">${statusDisplay}</td>
                <td class="text-center">${currentRent}</td>
                <td class="text-center">${formatNumberWithParentheses(element.currency, element.revenue_all_time)}</td>
                <td class="text-center">${formatNumberWithParentheses(element.currency, element.revenue_ytd)}</td>
                <td class="text-center text-danger">${formatNumberWithParentheses(element.currency, element.debt)}</td>
                <td class="text-center">${actionColumn}</td>
            `;
        case 'transaction':
            const period = element.period ? `(${element.period})` : "";
            return `
                <td>
                    <input class="form-check-input transaction-radio" type="radio" name="radioTransaction" value="${element.id}">
                </td>
                <td>${formatDateToDdmmyy(element.transaction_date)}</td>
                <td>${element.property}</td>
                <td class="transactionName">${element.category} ${period}</td>
                <td class="text-center">${formatNumberWithParentheses(element.currency, element.transaction_amount)}</td>
                <td>${element.comment}</td>
                <!-- Other cells as needed -->
            `;
        case 'propertyValuation':
            const value = element.value !== null ? formatNumberWithParentheses(element.currency, element.value) : '–';
            const debt = element.debt !== null ? formatNumberWithParentheses(element.currency, element.debt) : '–';

            return `
                <td>
                    <input class="form-check-input propertyValuation-radio" type="radio" name="radioPropertyValuation" value="${element.id}">
                </td>
                <td>${formatDateToDdmmyy(element.date)}</td>
                <td class="text-center">${value}</td>
                <td class="text-center">${debt}</td>
                <!-- Add other fields as needed -->
            `;
        default:
            // Handle other cases or show an error message
            console.error('Unknown element type:', type);
    }
}

// Handle rendering of detailed element part of the page
function tableElementClickHandler(event) {
                
    event.preventDefault();

    const type = event.target.parentElement.classList[0].replace("Name", "");

    // Get the property ID from the data attribute
    const elementId = this.closest(`.${type}Row`).getAttribute(`data-${type}-id`);

    load_element_details(type, elementId);
}


function backToTableClickHandler(event) {
    event.preventDefault();

    // Extract what type of element is being dealt with
    const type = event.target.getAttribute("data-back-type");
    load_table(type);
}

// Pre-fill data for editing form
function preFillForm(type, elementId) {
    
    fetch(`/handling/${type}/${elementId}`)
    .then(response => response.json())
    .then(data => {
                
        switch (type) {
            case 'property':
                document.getElementById('id_name').value = data.name;
                document.getElementById('id_location').value = data.location;
                document.getElementById('id_address').value = data.address;
                document.getElementById('id_num_bedrooms').value = data.num_bedrooms;
                document.getElementById('id_area').value = data.area;
                chooseSelectedOption('currency', data.currency);
                // document.getElementById('id_property_value').value = data.property_value;
                break;
            case 'tenant':
                document.getElementById('id_first_name').value = data.first_name;
                document.getElementById('id_last_name').value = data.last_name;
                document.getElementById('id_phone').value = data.phone;
                document.getElementById('id_email').value = data.email;
                
                // Add current tenant's property to the selection of properties
                const propertySelect = document.getElementById('id_property'); // Find the 'property' select element in your form by its ID
                const option = document.createElement('option'); // Create a new option element
                option.value = data.property_id; // Set the value to the property ID (not tenant ID)
                option.text = data.property;
                propertySelect.appendChild(option); // Append the option to the select element
                option.selected = true;

                document.getElementById('id_lease_start').value = data.renting_since;
                document.getElementById('id_payday').value = data.payday;
                chooseSelectedOption('currency', data.rent_currency);
                document.getElementById('id_lease_rent').value = data.rent_rate;
                break;
            case 'transaction':
                chooseSelectedOption('property', data.property);
                document.getElementById('id_date').value = data.transaction_date;
                chooseSelectedOption('category', data.category);
                document.getElementById('id_period').value = data.period;
                chooseSelectedOption('currency', data.currency);
                document.getElementById('id_amount').value = data.amount;
                document.getElementById('id_comment').value = data.comment;
                break;
            case 'propertyValuation':
                console.log(`preFillForm. propertyValuation ${data.property_id}`)
                document.getElementById('id_capital_structure_date').value = data.date;
                document.getElementById('id_capital_structure_value').value = data.value;
                document.getElementById('id_capital_structure_debt').value = data.debt;
                document.getElementById('id_property_valuation').value = data.property_id;
                
                // Making the proper currency selection
                // Get the select element
                const selectElement = document.getElementById('id_currency');

                // Iterate through the options
                for (let i = 0; i < selectElement.options.length; i++) {
                    let option = selectElement.options[i];

                    // Check if the option's value matches the desired currencyValue
                    if (option.value === data.currency) {
                        // Set the selected attribute for the matching option
                        option.selected = true;
                    }
                }
                // document.getElementById('id_currency').value = data.currency;
                break;
        }
    })
    .catch(error => console.log(error));

    document.querySelectorAll('.modal-footer .btn-primary').forEach(button => {
        button.textContent = 'Save changes';
    });

}

function load_element_details(type, elementId) {
    
    const Type = type.charAt(0).toUpperCase() + type.slice(1);

    // Show the [type] element and hide other views
    document.getElementById(`${type}Table`).style.display = 'none';
    document.querySelector('.new-entry-button').style.display = 'none';
    document.getElementById(`${type}DetailsContainer`).style.display = '';

    fetch(`/handling/${type}/${elementId}`)
    .then(response => {
        if (response.ok) {
            return response.json();
        } else {
            return response.json().then(data => {
                throw new Error(data.Error);
            });
        }
    })
    .then(element => {

        document.getElementById('datePicker').value = element.app_date;
    
        switch(type) {
            case 'property':

                // Show the page name
                document.querySelector('h2').innerHTML = `${Type}: ${element.name}`;
                
                // Populate the parameters in the dashboard cards
                document.querySelector('#propertyLocationCard .display-4').textContent = element.location;
                document.querySelector('#propertyBedroomsCard .display-4').textContent = element.num_bedrooms;
                document.querySelector('#propertyAreaCard .display-4').textContent = 
                    (typeof element.area === 'number' && !isNaN(element.area)) ? element.area.toFixed(0) : 'NA';
                // document.querySelector('#propertyValueCard .display-4').textContent = 
                //     (typeof element.property_value === 'number' && !isNaN(element.property_value)) ? formatNumberWithParentheses(element.currency, element.property_value) + "k" : 'NA';
                
                let valueText;
                if (typeof element.property_value === 'number' && !isNaN(element.property_value)) {
                    valueText = (element.property_value === 0) ? element.currency : formatNumberWithParentheses(element.currency, element.property_value) + "k";
                } else {
                    valueText = 'NA';
                }

                document.querySelector('#propertyValueCard .display-4').textContent = valueText;
                
                // Populate P&L table
                populatePropertyProfitAndLossTable(element);

                // Populate Payments schedule table
                createPropertyPaymentsTable(element.months, element.rows);

                // Show actual chart settings               
                updateFrequencySetting(element.chart_settings["frequency"])
                chooseSelectedOption("chartTimeline", element.chart_settings["timeline"]);

                document.getElementById("chartDateTo").value = element.chart_settings["To"];
                document.getElementById("chartDateFrom").value = element.chart_settings["From"];
                
                typeChartInitialization("propertyValuation", element.chart_data);

                const addDataButton = document.getElementById('addPropertyValuationDataButton');
                const editDataButton = document.getElementById('editPropertyValuationDataButton');

                if (!addDataButton && !editDataButton) {
                    // Adding buttons
                    // Create Add Data button
                    const addDataButton = document.createElement('button');
                    addDataButton.type = 'button';
                    addDataButton.className = 'btn btn-secondary me-2 new-entry-button';
                    addDataButton.dataset.newType = 'propertyValuation';
                    addDataButton.id = 'addPropertyValuationDataButton';
                    addDataButton.innerText = 'Add Data';

                    // Create Edit Data button
                    const editDataButton = document.createElement('button');
                    editDataButton.type = 'button';
                    editDataButton.className = 'btn btn-secondary edit-entry-button';
                    editDataButton.dataset.editType = 'propertyValuation';
                    editDataButton.id = 'editPropertyValuationDataButton';
                    editDataButton.innerText = 'Edit Data';
                    editDataButton.dataset.bsToggle="modal";
                    editDataButton.dataset.bsTarget = '#propertyEditValuationModalDiv';

                    // Add event listeners to the buttons
                    addDataButton.addEventListener('click', elementActionClickHandler);
                    editDataButton.addEventListener('click', () => {
                        console.log(`load_element_details`);
                        load_table("propertyValuation");
                    });

                    // Append buttons to the container
                    const dataButtonsContainer = document.getElementById('dataButtonsContainer');
                    dataButtonsContainer.appendChild(addDataButton);
                    dataButtonsContainer.appendChild(editDataButton);
                }

                // function openAddEditDataModal(action) {
                //     // Update modal title based on the action
                //     document.getElementById('chartModalLabel').innerText = `${action} Modal Title`;

                //     // Trigger the modal opening
                //     const addEditDataModal = new bootstrap.Modal(document.getElementById('addEditDataModal'));
                //     addEditDataModal.show();
                //     // Additional logic for fetching data or handling the modal content can be added here
                // }

                break;

            case 'tenant':
                // Show the page name
                document.querySelector('h2').innerHTML = `${Type}: ${element.first_name} ${element.last_name === null ? "" : element.last_name}`;

                // Populate the parameters in the dashboard cards
                document.querySelector('#tenantPropertyCard .display-4').textContent = element.property;
                document.querySelector('#tenantMovedInCard .display-4').textContent = formatDateToDdmmyy(element.renting_since);
                document.querySelector('#tenantRentCard .display-4').textContent = 
                    (typeof element.rent_rate === 'number' && !isNaN(element.rent_rate)) ? formatNumberWithParentheses(element.rent_native_currency, element.rent_rate) : 'NA';
                document.querySelector('#tenantRevenueCard .display-4').textContent = 
                    (typeof element.all_time_rent === 'number' && !isNaN(element.all_time_rent)) ? formatNumberWithParentheses(element.rent_currency, element.all_time_rent) : 'NA';
                
                // Show actual chart settings               
                updateFrequencySetting(element.chart_settings["frequency"])
                chooseSelectedOption('chartTimeline', element.chart_settings['timeline']);
                
                document.getElementById("chartDateTo").value = element.chart_settings['To'];
                document.getElementById("chartDateFrom").value = element.chart_settings['From'];

                typeChartInitialization(type, element.chart_data);

                break;

            case 'transaction':
                break;
            default:
                // Handle other cases or show an error message
                console.error('Unknown element type:', type);
        }

        formatCards(type);

        // Add Vacate button and status info for tenants after all DOM elements are created
        if (type === 'tenant') {
            // Check if tenant is vacated (fallback to false if property doesn't exist)
            const isVacated = element.is_vacated || false;
            const willVacate = element.will_vacate || false;
            
            // Add status information to the tenant header
            const tenantHeader = document.querySelector('h2');
            let statusBadge = '';
            if (isVacated) {
                statusBadge = '<span class="badge bg-danger ms-2">Vacated</span>';
                if (element.left_property_at) {
                    statusBadge += `<small class="text-muted ms-2">on ${formatDateToDdmmyy(element.left_property_at)}</small>`;
                }
            } else if (willVacate) {
                statusBadge = '<span class="badge bg-warning ms-2">Will Vacate</span>';
                if (element.left_property_at) {
                    statusBadge += `<small class="text-muted ms-2">on ${formatDateToDdmmyy(element.left_property_at)}</small>`;
                }
            } else {
                statusBadge = '<span class="badge bg-success ms-2">Active</span>';
            }
            
            if (tenantHeader && !tenantHeader.querySelector('.badge')) {
                tenantHeader.innerHTML += statusBadge;
            }
            
            // Add Vacate button only for active tenants
            if (!isVacated && !willVacate) {
                // Use setTimeout to ensure buttons are fully rendered
                setTimeout(() => {
                    const editButton = document.getElementById(`edit${Type}Button`);
                    if (editButton && !document.getElementById('vacateTenantBtn')) {
                        const vacateButton = document.createElement('button');
                        vacateButton.type = 'button';
                        vacateButton.className = 'btn btn-warning me-2';
                        vacateButton.id = 'vacateTenantBtn';
                        vacateButton.innerHTML = '<i class="bi bi-door-open"></i> Vacate';
                        vacateButton.setAttribute('data-tenant-id', elementId);
                        
                        // Add event listener with tenant name
                        vacateButton.addEventListener('click', function() {
                            const tenantName = `${element.first_name} ${element.last_name || ''}`.trim();
                            showVacateModal(elementId, tenantName);
                        });
                        
                        // Insert before the edit button (in the right-side button group)
                        editButton.parentNode.insertBefore(vacateButton, editButton);
                    }
                }, 50);
            }
        }

    })
    .catch(error => {
        console.log(error);
    });

    const elementDetailsButtons = document.getElementById(`back-to-${type}-table`);
    if (!elementDetailsButtons) {
        // Create the "Back to Table", "Edit" and "Delete" buttons HTML
        const buttonsHTML = `
            <div class="d-flex justify-content-between mb-3">
                <button type="button" class="btn btn-primary" id="back-to-${type}-table" data-back-type="${type}">
                    Back to ${Type} table
                </button>
                <div>
                    <button type="button" class="btn btn-secondary me-2 edit-entry-button" data-${type}-id="${elementId}" data-edit-type="${type}" id="edit${Type}Button">
                        Edit
                    </button>
                    <button type="button" class="btn btn-danger" data-${type}-id="${elementId}" id="delete${Type}Button" data-delete-type="${type}" data-bs-toggle="modal" data-bs-target="#deleteConfirmationModal">
                        <i class="bi bi-trash3"></i>
                    </button>
                </div>
            </div>
        `;

        // Append the "Back to properties" button to the property details container
        document.getElementById(`${type}DetailsContainer`).insertAdjacentHTML('beforebegin', buttonsHTML);
        
        // Add a click event listener to the button to go back to [Type] table
        const backButton = document.getElementById(`back-to-${type}-table`);
        backButton.addEventListener('click', backToTableClickHandler);

        // Add a click event listener to the button to edit property
        const editButton = document.getElementById(`edit${Type}Button`);
        editButton.addEventListener('click', elementActionClickHandler);

        // // Add a click event listener to Valuation button
        // const valuationButton = document.getElementById('valuationPropertyButton');
        // if (valuationButton) {
        //     valuationButton.addEventListener('click', valuationButtonClickHandler);
        // }

        // // Add a click event listener to the button to delete property
        // const deleteButton = document.getElementById('confirmDeleteButton');
        // deleteButton.addEventListener('click', deleteElementHandler);
    }
    
}

// Function to populate the Property P&L table
function populatePropertyProfitAndLossTable(element) {
    const tableBody = document.querySelector('.pnl-table tbody');
    
    // Clear existing table rows
    tableBody.innerHTML = '';
    
    // Add rows for Rent, expenses, Total Expenses, and Net Income
    tableBody.appendChild(createTableRow('Rent', element.rent.ytd, element.rent.all_time, element.currency));
    tableBody.appendChild(createTableRow('Total Income', element.rent.ytd, element.rent.all_time, element.currency, isBold=true));
    
    for (const category in element.expenses) {
        if (element.expenses.hasOwnProperty(category) && category !== 'total') {
            const data = element.expenses[category];
            tableBody.appendChild(createTableRow(category, data.ytd, data.all_time, element.currency));
        }
    }
    
    tableBody.appendChild(createTableRow('Total Expenses', element.expenses.total.ytd, element.expenses.total.all_time, element.currency, isBold=true));
    tableBody.appendChild(createTableRow('Net Income', element.net_income.ytd, element.net_income.all_time, element.currency, isBold=true));
}

// Function to create a table row for a category
function createTableRow(category, YTD, allTime, currency, isBold = false) {
    const row = document.createElement('tr');
    
    if (isBold) {
        row.classList.add('fw-semibold');
    }

    const categoryCell = document.createElement('td');
    categoryCell.textContent = category;
    
    const YTDCell = document.createElement('td');
    YTDCell.className = "text-center";
    YTDCell.textContent = formatNumberWithParentheses(currency, YTD);
    
    const allTimeCell = document.createElement('td');
    allTimeCell.className = "text-center";
    allTimeCell.textContent = formatNumberWithParentheses(currency, allTime);
    
    row.appendChild(categoryCell);
    row.appendChild(YTDCell);
    row.appendChild(allTimeCell);
    
    return row;
}

function createPropertyPaymentsTable(months, rows) {
    const table = document.getElementById('paymentScheduleTable');
    const thead = table.querySelector('thead');
    const headerRow = thead.querySelector('tr');
    headerRow.innerHTML = "<th></th>";

    // Loop through the months and create header cells
    months.forEach(month => {
        const monthHeaderCell = document.createElement('th');
        monthHeaderCell.className = 'text-center';
        monthHeaderCell.textContent = month;
        headerRow.appendChild(monthHeaderCell);
    });

    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = table.querySelector('tbody');
    tbody.innerHTML = "";

    // Loop through the rows and create rows and cells
    for (const key in rows) {
        if (rows.hasOwnProperty(key)) {
            const colours = rows[key];
            const rowElement = document.createElement('tr');

            // Create the row name cell
            const nameCell = document.createElement('th');
            nameCell.scope = 'row';
            nameCell.className = 'row-name';
            nameCell.textContent = key;
            rowElement.appendChild(nameCell);

            // Loop through the cells and create cells with appropriate classes
            colours.forEach(color => {
                const cellElement = document.createElement('td');
                cellElement.className = `text-center ${color}-circle`;
                rowElement.appendChild(cellElement);
            });

            tbody.appendChild(rowElement);
        }
    }
}

// Format date string to dd-mmm-yy
function formatDateToDdmmyy(dateString) {
    
    if (dateString === null) {
        return '–'
    }

    const options = { year: '2-digit', month: 'short', day: 'numeric' };
    const date = new Date(dateString);

    const formattedDate = date.toLocaleDateString('en-GB', options);
  
    // Manually add dashes between elements
    const parts = formattedDate.split(' ');
    return parts[0] + '-' + parts[1] + '-' + parts[2];
}

// Function to format numbers with parentheses for negatives
function formatNumberWithParentheses(currency, number) {
    if (number < 0) {
        return `(${currency}${Math.abs(number).toLocaleString()})`;
    } else if (number === 0) {
        return '–';
    };
    return `${currency}${number.toLocaleString()}`;
}

// Add listeners to radio buttons on transaction table
function addTransactionValuationListeners(type) {

    const Type = type.charAt(0).toUpperCase() + type.slice(1);

    // Select the radio buttons and buttons
    const radioButtons = document.querySelectorAll(`.${type}-radio`);
    const editButton = document.getElementById(`edit${Type}Button`);
    const deleteButton = document.getElementById(`delete${Type}Button`);
    
    // Add a change event listener to the radio buttons
    radioButtons.forEach((radio) => {
        radio.addEventListener('change', () => {
            // Check if any radio button is selected
            const anyRadioButtonSelected = Array.from(radioButtons).some((radio) => radio.checked);
            
            // Enable or disable the buttons accordingly
            editButton.disabled = !anyRadioButtonSelected;
            deleteButton.disabled = !anyRadioButtonSelected;
        });
    });
}

// Disable property valuation Edit form Edit and Delete buttons
function disableEditDeleteButtons() {
    const editButton = document.getElementById('editPropertyValuationButton');
    const deleteButton = document.getElementById('deletePropertyValuationButton');
    const myModal = new bootstrap.Modal(document.getElementById('propertyEditValuationModalDiv'));

    // Add an event listener when the modal is hidden
    myModal._element.addEventListener('hidden.bs.modal', function() {
        // Disable Edit and Delete buttons
        editButton.disabled = true;
        deleteButton.disabled = true;
    });
}

// Property Valuation delete click handler
function propertyValuationDeleteElementHandler(event) {

    event.preventDefault();

    // Get element ID from delete button

        const selectedRadio = document.querySelector('input[name="radioPropertyValuation"]:checked');
        
        let elementId;
        if (selectedRadio) {
            elementId = selectedRadio.value;
            console.log(`Selected radio button value: ${elementId}`);
        } else {
            throw new Error("Couldn't retrieve radio button value");
        }

    const csrftoken = getCookie('csrftoken');

    fetch(`/handling/propertyValuation/${elementId}`, {
        method: 'DELETE',
        headers: {
            'X-CSRFToken': csrftoken
        }
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        } else {
            throw new Error("Property valuation deletion failed");
        }
    })
    .then(data => {
        // Close the Delete Confirmation Modal
        let modalReference = document.getElementById("propertyValuationDeleteConfirmationModal");
        let confirmationModal = bootstrap.Modal.getInstance(modalReference);
        confirmationModal.hide();
        
        const successDiv = document.getElementById("successModal");

        // Show success modal or message
        const successModal = new bootstrap.Modal(successDiv);
        successModal.show();
        
        // Pass the type to success div
        successDiv.setAttribute(`data-success-type`, "propertyValuation");

        // Edit success modal message
        const successMessage = data.message.charAt(0).toUpperCase() + data.message.slice(1)
        document.querySelector('#successModal .modal-body').textContent = successMessage;
        document.querySelector('#successModal a').style.display = 'none';

        updateChart(window.myChart, document.getElementById("id_chartTimeline"));
    })
    .catch(error => {
        console.error('Error:', error);
    });    
}

// Vacate tenant functionality
function showVacateModal(tenantId) {
    // Create modal HTML
    const modalHTML = `
        <div class="modal fade" id="vacateModal" tabindex="-1" aria-labelledby="vacateModalLabel" aria-hidden="true">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="vacateModalLabel">Set Vacate Date</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <form id="vacateForm">
                            <div class="mb-3">
                                <label for="vacate_date" class="form-label">Vacate Date</label>
                                <input type="date" class="form-control" id="vacate_date" name="vacate_date" required>
                                <div class="form-text">Select the date when the tenant will vacate the property</div>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-warning" id="confirmVacateBtn">Set Vacate Date</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Remove existing modal if any
    const existingModal = document.getElementById('vacateModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Add modal to body
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    
    // Set default value to today, but allow past dates
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('vacate_date').value = today;
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('vacateModal'));
    modal.show();
    
    // Add event listener to confirm button
    document.getElementById('confirmVacateBtn').addEventListener('click', function() {
        const vacateDate = document.getElementById('vacate_date').value;
        if (!vacateDate) {
            alert('Please select a vacate date');
            return;
        }
        
        vacateTenant(tenantId, vacateDate);
    });
}

function addVacateButtonListeners() {
    const vacateButtons = document.querySelectorAll('.vacate-btn');
    vacateButtons.forEach(button => {
        button.addEventListener('click', function() {
            const tenantId = this.getAttribute('data-tenant-id');
            const tenantName = this.getAttribute('data-tenant-name');
            
            // Create and show vacate modal
            showVacateModal(tenantId, tenantName);
        });
    });
}

function showVacateModal(tenantId, tenantName) {
    // Create modal HTML if it doesn't exist
    let modal = document.getElementById('vacateModal');
    if (!modal) {
        const modalHTML = `
            <div class="modal fade" id="vacateModal" tabindex="-1" aria-labelledby="vacateModalLabel" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="vacateModalLabel">Vacate Tenant</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <p>Set vacation date for tenant: <strong id="vacateModalTenantName"></strong></p>
                            <div class="mb-3">
                                <label for="vacateDate" class="form-label">Vacation Date</label>
                                <input type="date" class="form-control" id="vacateDate" required>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-warning" id="confirmVacateBtn">Confirm Vacate</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        modal = document.getElementById('vacateModal');
        
        // Add event listener to confirm button
        document.getElementById('confirmVacateBtn').addEventListener('click', function() {
            const vacateDate = document.getElementById('vacateDate').value;
            const tenantId = modal.getAttribute('data-tenant-id');
            
            if (vacateDate) {
                vacateTenant(tenantId, vacateDate);
            } else {
                alert('Please select a vacation date');
            }
        });
    }
    
    // Set tenant info and show modal
    document.getElementById('vacateModalTenantName').textContent = tenantName;
    modal.setAttribute('data-tenant-id', tenantId);
    
    // Set default date to today
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('vacateDate').value = today;
    
    // Show modal
    const bootstrapModal = new bootstrap.Modal(modal);
    bootstrapModal.show();
}

function vacateTenant(tenantId, vacateDate) {
    const formData = new FormData();
    formData.append('vacate_date', vacateDate);
    
    fetch(`/vacate-tenant/${tenantId}`, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('vacateModal'));
            modal.hide();
            
            // Show success message
            alert(data.message);
            
            // Check if we're on the tenant details page or table view
            const tenantDetailsContainer = document.getElementById('tenantDetailsContainer');
            const tenantTable = document.getElementById('tenantTable');
            
            if (tenantDetailsContainer && tenantDetailsContainer.style.display !== 'none') {
                // We're on tenant details page - reload the details
                load_element_details('tenant', tenantId);
            } else if (tenantTable && tenantTable.style.display !== 'none') {
                // We're on tenant table page - reload the table
                load_table('tenant');
            }
        } else {
            alert('Error: ' + (data.error || 'Unknown error occurred'));
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error occurred while processing the request');
    });
}

// Helper function to get CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}