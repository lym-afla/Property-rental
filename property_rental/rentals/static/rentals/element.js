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

});

function load_table(type) {

    console.log(`loading table ${type}`)

    const Type = type.charAt(0).toUpperCase() + type.slice(1);

    // Show the [type] table and hide other views
    document.getElementById(`${type}Table`).style.display = '';
    document.querySelector('.new-entry-button').style.display = '';
    document.getElementById(`${type}DetailsContainer`).style.display = 'none';
    
    // Delete event listeners from the buttons on detailed [Type] page
    const detailElementCheck = document.getElementById(`back-to-${type}-table`);
    if (detailElementCheck) {
        // document.getElementById('confirmDeleteButton').removeEventListener('click', deleteElementHandler);
        document.getElementById(`back-to-${type}-table`).removeEventListener('click', backToTableClickHandler);
        document.getElementById(`edit${Type}Button`).removeEventListener('click', elementActionClickHandler);
        detailElementCheck.parentElement.remove();
    } else if (type === 'transaction') {
        // Remove event listeners for other types
        // document.getElementById('confirmDeleteButton').removeEventListener('click', deleteElementHandler);
        // document.getElementById(`edit${Type}Button`).removeEventListener('click', elementActionClickHandler);

        // Assign transaction related event listeners for editing and deleting elements
        // document.getElementById('confirmDeleteButton').addEventListener('click', deleteElementHandler);
        document.getElementById(`edit${Type}Button`).addEventListener('click', elementActionClickHandler);
    }
    
    // Show the page name
    document.querySelector('h2').innerHTML = (type === 'property') ? 'Properties' : `${Type}s`;

    fetchTableData(type);
}

function fetchTableData(type) {

    fetch(`/table-data/${type}`)
    .then(response => response.json())
    .then(data => {
        const tbody = document.querySelector(`#${type}Table tbody`);
        tbody.innerHTML = '';  // Clear the table body

        document.getElementById('datePicker').value = data[0];
        console.log(data[0]);

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
            if (type != 'transaction') {
                const rowName = row.querySelector(`.${type}Name`);
                rowName.removeEventListener('click', tableElementClickHandler);
                rowName.addEventListener('click', tableElementClickHandler);
            }

        });

        if (type === 'transaction') {
            addTransactionListeners();
        }
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
            `
        case 'tenant':
            const currentRent = (element.lease_rent === 'No rent history for the Tenant') ? "-" : formatNumberWithParentheses(element.currency, element.lease_rent);
            return `
                <td class="tenantName"><a href="">${element.first_name}</a></td>
                <td class="text-center">${element.property}</td>
                <td class="text-center">${formatDateToDdmmyy(element.lease_start)}</td>
                <td class="text-center">${currentRent}</td>
                <td class="text-center">${formatNumberWithParentheses(element.currency, element.revenue_all_time)}</td>
                <td class="text-center">${formatNumberWithParentheses(element.currency, element.revenue_ytd)}</td>
                <td class="text-center">${formatNumberWithParentheses(element.currency, element.debt)}</td>
            `
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
            `
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

// // Delete click handler
// function deleteElementHandler(event) {

//     event.preventDefault();

//     // Extract what type of element is being dealt with
//     const deleteButton = document.getElementById(`deleteButton`);
//     const type = deleteButton.getAttribute("data-delete-type");
    
//     let elementId;

//     // Get element ID from delete button
//     if (type === "transaction") {
//         const selectedRadio = document.querySelector('input[name="radioTransaction"]:checked');

//         if (selectedRadio) {
//             elementId = selectedRadio.value;
//             console.log(`Selected radio button value: ${elementId}`);
//         } else {
//             throw new Error("Couldn't retrieve radio button value");
//         }
   
//     } else { 
//         elementId = deleteButton.getAttribute(`data-${type}-id`);
//     }

//     const csrftoken = getCookie('csrftoken');

//     fetch(`/handling/${type}/${elementId}`, {
//         method: 'DELETE',
//         headers: {
//             'X-CSRFToken': csrftoken
//         }
//     })
//     .then(response => {
//         if (response.ok) {
//             return response.json();
//         } else {
//             throw new Error(`${type} deletion failed`);
//         }
//     })
//     .then(data => {
//         // Close the Delete Confirmation Modal
//         let modalReference = document.getElementById("deleteConfirmationModal");
//         let confirmationModal = bootstrap.Modal.getInstance(modalReference);
//         confirmationModal.hide();
        
//         const successDiv = document.getElementById('successModal');

//         // Show success modal or message
//         const successModal = new bootstrap.Modal(successDiv);
//         successModal.show();
        
//         // Pass the type to success div
//         successDiv.setAttribute(`data-success-type`, type);

//         // Edit success modal message
//         const successMessage = data.message.charAt(0).toUpperCase() + data.message.slice(1)
//         document.querySelector('#successModal .modal-body').textContent = successMessage;
//         document.querySelector('#successModal a').style.display = 'none';
//     })
//     .catch(error => {
//         console.error('Error:', error);
//     });    
// }

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
                document.getElementById('id_property_value').value = data.property_value;
                break;
            case 'tenant':
                document.getElementById('id_first_name').value = data.first_name;
                document.getElementById('id_last_name').value = data.last_name;
                document.getElementById('id_phone').value = data.phone;
                document.getElementById('id_email').value = data.email;
                
                // Add current tenant's property to the selection of properties
                const propertySelect = document.getElementById('id_property'); // Find the 'property' select element in your form by its ID
                const option = document.createElement('option'); // Create a new option element
                option.value = data.id; // Set the value to the property ID
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
        }
    })
    .catch(error => console.log(error));

    document.querySelector('.modal-footer .btn-primary').textContent = 'Save changes';

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
        console.log(element.app_date);
    
        switch(type) {
            case 'property':
                console.log(type);
                // Show the page name
                document.querySelector('h2').innerHTML = `${Type}: ${element.name}`;
                
                // Populate the parameters in the dashboard cards
                document.querySelector('#propertyLocationCard .display-4').textContent = element.location;
                document.querySelector('#propertyBedroomsCard .display-4').textContent = element.num_bedrooms;
                document.querySelector('#propertyAreaCard .display-4').textContent = 
                    (typeof element.area === 'number' && !isNaN(element.area)) ? element.area.toFixed(0) : 'NA';
                document.querySelector('#propertyValueCard .display-4').textContent = 
                    (typeof element.property_value === 'number' && !isNaN(element.property_value)) ? formatNumberWithParentheses(element.currency, element.property_value) + "k" : 'NA';
                
                // Populate P&L table
                populatePropertyProfitAndLossTable(element);

                // Populate Payments schedule table
                createPropertyPaymentsTable(element.months, element.rows);
                
                break;

            case 'tenant':
                console.log(type);
                // Show the page name
                document.querySelector('h2').innerHTML = `${Type}: ${element.first_name} ${element.last_name === null ? "" : element.last_name}`;

                // Populate the parameters in the dashboard cards
                document.querySelector('#tenantPropertyCard .display-4').textContent = element.property;
                document.querySelector('#tenantMovedInCard .display-4').textContent = formatDateToDdmmyy(element.renting_since);
                document.querySelector('#tenantRentCard .display-4').textContent = 
                    (typeof element.rent_rate === 'number' && !isNaN(element.rent_rate)) ? formatNumberWithParentheses(element.rent_currency, element.rent_rate) : 'NA';
                document.querySelector('#tenantRevenueCard .display-4').textContent = 
                    (typeof element.all_time_rent === 'number' && !isNaN(element.all_time_rent)) ? formatNumberWithParentheses(element.rent_currency, element.all_time_rent) : 'NA';
                break;

            case 'transaction':
                break;
            default:
                // Handle other cases or show an error message
                console.error('Unknown element type:', type);
        }

        formatCards(type);

    })
    .catch(error => {
        console.log(error);
    });

    const propertyDetailsButtons = document.getElementById(`back-to-${type}-table`);
    if (!propertyDetailsButtons) {
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
                    <button type="button" class="btn btn-danger" data-${type}-id="${elementId}" id="deleteButton" data-delete-type="${type}" data-bs-toggle="modal" data-bs-target="#deleteConfirmationModal">
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
        if (element.expenses.hasOwnProperty(category)) {
            const data = element.expenses[category];
            tableBody.appendChild(createTableRow(category, data.ytd, data.all_time, element.currency));
        }
    }

    // Initialize total expenses
    let totalYTDExpenses = 0;
    let totalAllTimeExpenses = 0;

    // Iterate through the expenses data and sum up the values
    for (const category in element.expenses) {
        totalYTDExpenses += element.expenses[category]['ytd'];
        totalAllTimeExpenses += element.expenses[category]['all_time'];
    }
    
    tableBody.appendChild(createTableRow('Total Expenses', totalYTDExpenses, totalAllTimeExpenses, element.currency, isBold=true));
    tableBody.appendChild(createTableRow('Net Income', element.rent.ytd + totalYTDExpenses, element.rent.all_time + totalAllTimeExpenses, element.currency, isBold=true));
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
        return `(${currency}${Math.abs(number.toFixed(0)).toLocaleString()})`;
    } else if (number === 0) {
        return '–';
    };
    return `${currency}${number.toLocaleString()}`;
}

// Add listeners to radio buttons on transaction table
function addTransactionListeners() {
    // Select the radio buttons and buttons
    const radioButtons = document.querySelectorAll('.transaction-radio');
    const editButton = document.getElementById('editTransactionButton');
    const deleteButton = document.getElementById('deleteButton');
    
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

// Make the default selection of the respective currency option
function chooseSelectedOption(option, choice) {
    const selectedElement = document.getElementById(`id_${option}`);
    // Loop through each option in the select element
    for (let i = 0; i < selectedElement.options.length; i++) {
        const optionElement = selectedElement.options[i];
        // Check if the option's value matches the value to match
        const checkText = (option === 'category') ? optionElement.value : optionElement.textContent;
        if (checkText === choice) {
        // Set the selected attribute to make this option selected
        optionElement.selected = true;
        break; // Exit the loop once a match is found
        }
    }
}