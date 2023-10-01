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
    document.getElementById(`${type}Table`).style.display = 'block';
    document.querySelector('.new-entry-button').style.display = 'block';
    document.getElementById(`${type}DetailsContainer`).style.display = 'none';
    
    // Delete event listeners from the buttons on detailed [Type] page
    const detailElementCheck = document.getElementById(`back-to-${type}-table`);
    if (detailElementCheck) {
        document.getElementById('confirmDeleteButton').removeEventListener('click', deleteElementHandler);
        document.getElementById(`back-to-${type}-table`).removeEventListener('click', backToTableClickHandler);
        document.getElementById(`edit${Type}Button`).removeEventListener('click', elementActionClickHandler);
        detailElementCheck.parentElement.remove();
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

        data.forEach(element => {

            const row = document.createElement('tr');
            row.className = `${type}Row`;
            row.setAttribute(`data-${type}-id`, element.id);

            row.innerHTML = fillRow(type, element);

            tbody.appendChild(row);

            // Need to remove event listeners if already created to prevent duplication
            const rowName = row.querySelector(`.${type}Name`);
            rowName.removeEventListener('click', tableElementClickHandler);
            rowName.addEventListener('click', tableElementClickHandler);

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
            const circleClass = element.status === 'rented' ? 'green-circle' : 'red-circle';

            return `
                <td class="propertyName"><a href="">${element.name}</td>
                <td class="text-center">${element.location}</td>
                <td class="text-center">${element.rent_since}</td>
                <td class="text-center"><i class="fas fa-circle ${circleClass}"></i></td>
                <!-- Other cells as needed -->
            `
        case 'tenant':
            return `
                <td class="tenantName"><a href="">${element.first_name}</td>
                <td class="text-center">${element.property}</td>
                <td class="text-center">${formatDateToDdmmyy(element.lease_start)}</td>
                <td class="text-center">${element.currency}${element.lease_rent}</i></td>
                <!-- Other cells as needed -->
            `
        case 'transaction':
            break;
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
    const elementId = this.closest('.propertyRow').getAttribute(`data-${type}-id`);

    load_element_details(type, elementId);
}


function backToTableClickHandler(event) {
    event.preventDefault();

    // Extract what type of element is being dealt with
    const type = event.target.getAttribute("data-back-type");
    load_table(type);
}

// Delete click handler
function deleteElementHandler(event) {

    event.preventDefault();

    // Extract what type of element is being dealt with
    const deleteButton = document.getElementById(`deleteButton`);
    const type = deleteButton.getAttribute("data-delete-type");
    
    // Get element ID from delete button
    const elementId = deleteButton.getAttribute(`data-${type}-id`);
    
    const csrftoken = getCookie('csrftoken');

    fetch(`/handling/${type}/${elementId}`, {
        method: 'DELETE',
        headers: {
            'X-CSRFToken': csrftoken
        }
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        } else {
            throw new Error(`${type} deletion failed`);
        }
    })
    .then(data => {
        // Close the Delete Confirmation Modal
        let modalReference = document.getElementById("deleteConfirmationModal");
        let confirmationModal = bootstrap.Modal.getInstance(modalReference);
        confirmationModal.hide();
        
        const successDiv = document.getElementById('successModal');

        // Show success modal or message
        const successModal = new bootstrap.Modal(successDiv);
        successModal.show();
        
        // Pass the type to success div
        successDiv.setAttribute(`data-success-type`, type);

        // Edit success modal message
        const successMessage = data.message.charAt(0).toUpperCase() + data.message.slice(1)
        document.querySelector('#successModal .modal-body').textContent = successMessage;
        document.querySelector('#successModal a').style.display = 'none';
    })
    .catch(error => {
        console.error('Error:', error);
    });    
}

// Pre-fill data for editing form
function preFillForm(type) {
    
    switch (type) {
        case 'property':
            document.getElementById('id_name').value = document.querySelector('h2').innerHTML.replace('Property: ', '');
            document.getElementById('id_location').value = document.querySelector('#propertyLocationCard .display-4').textContent;
            document.getElementById('id_num_bedrooms').value = document.querySelector('#propertyBedroomsCard .display-4').textContent;
            let area = document.querySelector('#propertyAreaCard .display-4').textContent;
            area = (area === "NA") ? '' : area;
            document.getElementById('id_area').value = area;
            let value = document.querySelector('#propertyValueCard .display-4').textContent;
            value = (value === "NA") ? '' : value;
            document.getElementById('id_property_value').value = value;

    }

    document.querySelector('.modal-footer .btn-primary').textContent = 'Save changes';

}

function load_element_details(type, elementId) {
    
    const Type = type.charAt(0).toUpperCase() + type.slice(1);

    // Show the [type] element and hide other views
    document.getElementById(`${type}Table`).style.display = 'none';
    document.querySelector('.new-entry-button').style.display = 'none';
    document.getElementById(`${type}DetailsContainer`).style.display = 'block';

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

        // Show the page name
        document.querySelector('h2').innerHTML = `${Type}: ${element.name}`;
    
        switch(type) {
            case 'property':
                // Populate the parameters in the dashboard cards
                document.querySelector('#propertyLocationCard .display-4').textContent = element.location;
                document.querySelector('#propertyBedroomsCard .display-4').textContent = element.num_bedrooms;
                document.querySelector('#propertyAreaCard .display-4').textContent = 
                    (typeof element.area === 'number' && !isNaN(element.area)) ? element.area.toFixed(0) : 'NA';
                document.querySelector('#propertyValueCard .display-4').textContent = 
                    (typeof element.property_value === 'number' && !isNaN(element.property_value)) ? element.property_value.toFixed(0) : 'NA';

                // // After populating the cards, set their heights
                // setLocationCardHeight();

            case 'tenant':
                break;
            case 'transaction':
                break;
            default:
                // Handle other cases or show an error message
                console.error('Unknown element type:', type);
        }
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
                    Back to ${type} table
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
        propertyDetailsContainer.insertAdjacentHTML('beforebegin', buttonsHTML);
        
        // Add a click event listener to the button to go back to [Type] table
        const backButton = document.getElementById(`back-to-${type}-table`);
        backButton.addEventListener('click', backToTableClickHandler);

        // Add a click event listener to the button to edit property
        const editButton = document.getElementById(`edit${Type}Button`);
        editButton.addEventListener('click', elementActionClickHandler);

        // Add a click event listener to the button to delete property
        const deleteButton = document.getElementById('confirmDeleteButton');
        deleteButton.addEventListener('click', deleteElementHandler);
    }
    
}

// Format date string to dd-mmm-yy
function formatDateToDdmmyy(dateString) {
    const options = { year: '2-digit', month: 'short', day: 'numeric' };
    const date = new Date(dateString);

    const formattedDate = date.toLocaleDateString('en-GB', options);
  
    // Manually add dashes between elements
    const parts = formattedDate.split(' ');
    return parts[0] + '-' + parts[1] + '-' + parts[2];
}