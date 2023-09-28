document.addEventListener('DOMContentLoaded', function() {

    // By default, load the main table
    load_property_table();

    // Add event listener to the "New Property" button
    const newPropertyButton = document.getElementById('newPropertyButton');
    newPropertyButton.addEventListener('click', entryClickHandler);

});

function load_property_table() {
    
    // Show the property table and hide other views
    document.getElementById('propertiesTable').style.display = 'block';
    document.getElementById('newPropertyButton').style.display = 'block';
    
    const propertyDetailsButtons = document.getElementById('backToProperties');
    if (propertyDetailsButtons) {
        document.getElementById('confirmDeleteButton').removeEventListener('click', deleteClickHandler);
        document.getElementById('backToProperties').removeEventListener('click', backToPropertiesClickHandler);
        document.getElementById('editPropertyButton').removeEventListener('click', editClickHandler);
        propertyDetailsButtons.parentElement.remove();
    }
    
    document.getElementById('propertyDetailsContainer').style.display = 'none';

    // Show the page name
    document.querySelector('h2').innerHTML = `Properties`;

    fetch('/properties/table-data')
    .then(response => response.json())
    .then(data => {
        const tbody = document.querySelector('#propertiesTable tbody');
        tbody.innerHTML = '';  // Clear the table body

        data.forEach(property => {

            const row = document.createElement('tr');
            row.className = 'propertyRow';
            row.setAttribute('data-property-id', property.id);

            // Determine the circle class based on property.status
            const circleClass = property.status === 'rented' ? 'green-circle' : 'red-circle';

            row.innerHTML = `
                    <td class="propertyName"><a href="">${property.name}</td>
                    <td class="text-center">${property.location}</td>
                    <td class="text-center">${property.rent_since}</td>
                    <td class="text-center"><i class="fas fa-circle ${circleClass}"></i></td>
                    <!-- Add other cells as needed -->
                `;
            tbody.appendChild(row);

            // Need to remove event listeners if already created to prevent dupclication
            const rowName = row.querySelector('.propertyName');
            rowName.removeEventListener('click', propertyClickHandler);
            rowName.addEventListener('click', propertyClickHandler);

        });
    })
    .catch(error => {
        console.error('Error fetching property data', error);
    });
}

function propertyClickHandler(event) {
                
    event.preventDefault();

    // Get the property ID from the data attribute
    const propertyId = this.closest('.propertyRow').getAttribute('data-property-id');

    load_property_details(propertyId);
}

function load_property_details(propertyId) {

    // Show the property table and hide other views
    document.getElementById('propertiesTable').style.display = 'none';
    document.getElementById('newPropertyButton').style.display = 'none';
    const propertyDetailsContainer = document.getElementById('propertyDetailsContainer')
    propertyDetailsContainer.style.display = 'block';

    fetch(`/properties/${propertyId}`)
    .then(response => {
        if (response.ok) {
            return response.json();
        } else {
            return response.json().then(data => {
                throw new Error(data.Error);
            });
        }
    })
    .then(property => {
    
        // Show the page name
        document.querySelector('h2').innerHTML = `Property: ${property.name}`;
    
        // Populate the parameters in the dashboard cards
        document.querySelector('#propertyLocationCard .display-4').textContent = property.location;
        document.querySelector('#propertyBedroomsCard .display-4').textContent = property.num_bedrooms;
        document.querySelector('#propertyAreaCard .display-4').textContent = 
            (typeof property.area === 'number' && !isNaN(property.area)) ? property.area.toFixed(0) : 'NA';
        document.querySelector('#propertyValueCard .display-4').textContent = 
            (typeof property.property_value === 'number' && !isNaN(property.property_value)) ? property.property_value.toFixed(0) : 'NA';

        // After populating the cards, set their heights
        setLocationCardHeight();

    })
    .catch(error => {
        console.log(error);
    });

    const propertyDetailsButtons = document.getElementById('backToProperties');
    if (!propertyDetailsButtons) {
        // Create the "Back to properties", "Edit" and "Delete" buttons HTML
        const buttonsHTML = `
            <div class="d-flex justify-content-between mb-3">
                <button type="button" id="backToProperty" class="btn btn-primary">
                    Back to properties
                </button>
                <div>
                    <button type="button" class="btn btn-secondary me-2 edit-entry-button" data-property-id="${propertyId}" data-edit-type="property" id="editPropertyButton">
                        Edit
                    </button>
                    <button type="button" class="btn btn-danger" data-property-id="${propertyId}" id="deletePropertyButton" data-delete-type="property" data-bs-toggle="modal" data-bs-target="#deleteConfirmationModal">
                        <i class="bi bi-trash3"></i>
                    </button>
                </div>
            </div>
        `;

        // Append the "Back to properties" button to the property details container
        propertyDetailsContainer.insertAdjacentHTML('beforebegin', buttonsHTML);
        
        // Add a click event listener to the button to go back to properties
        const backButton = document.getElementById('backToProperties');
        backButton.addEventListener('click', backToPropertiesClickHandler);

        // Add a click event listener to the button to edit property
        const editButton = document.getElementById('editPropertyButton');
        editButton.addEventListener('click', entryClickHandler);

        // Add a click event listener to the button to delete property
        const deleteButton = document.getElementById('confirmDeleteButton');
        deleteButton.addEventListener('click', deleteClickHandler);
    }
}

// Edit click handler
function editClickHandler(event) {
    event.preventDefault();

    const action = event.target.getAttribute('data-edit-entry');

    // If the form has already been fetched, show the modal and return
    if (!formFetched[action]) {
        console.log(`Fetching ${action} form`);

        const createPropertyModal = document.getElementById('PropertyFormModal');
        
        // Fetch the form content
        fetch("/properties/new-property-form")
        .then(response => response.text())
        .then(formHTML => {
            // Inject the form content into the modal body
            createPropertyModal.innerHTML = formHTML;

            const modal = new bootstrap.Modal(document.getElementById('createPropertyModal'));
            modal.show();
            preFillPropertyForm();
            
            // Update the formFetched variable to indicate that the form has been fetched
            formFetched[action] = true;
        })
    } else {
        console.log(`${action} form already fetched`);
        const modal = new bootstrap.Modal(document.getElementById('createPropertyModal'));
        modal.show();
        preFillPropertyForm();
    }
}

// Pre-fill data for editing form
function preFillPropertyForm() {
    
    document.getElementById('id_name').value = document.querySelector('h2').innerHTML.replace('Property: ', '');
    document.getElementById('id_location').value = document.querySelector('#propertyLocationCard .display-4').textContent;
    document.getElementById('id_num_bedrooms').value = document.querySelector('#propertyBedroomsCard .display-4').textContent;
    let area = document.querySelector('#propertyAreaCard .display-4').textContent;
    area = (area === "NA") ? '' : area;
    document.getElementById('id_area').value = area;
    let value = document.querySelector('#propertyValueCard .display-4').textContent;
    value = (value === "NA") ? '' : value;
    document.getElementById('id_property_value').value = value;

    document.querySelector('.modal-footer .btn-primary').textContent = 'Save changes';

    // const form = document.querySelector('#createPropertyForm');
    // form.removeEventListener('submit', submitSaveHandler);
    // form.removeEventListener('submit', submitEditProperty);
    // form.addEventListener('submit', submitEditProperty);
}

// Delete click handler
function deleteClickHandler(event) {

    event.preventDefault();
    const propertyId = document.getElementById('deletePropertyButton').getAttribute('data-property-id');
    delete_property(propertyId);
    
}

function backToPropertiesClickHandler(event) {
    event.preventDefault();
    load_property_table();
}

// On property details page make the height of the first card to match the height of the rest
function setLocationCardHeight() {
    const locationCard = document.getElementById('propertyLocationCard');
    const areaCard = document.getElementById('propertyAreaCard');

    const areaCardHeight = areaCard.querySelector('.card').offsetHeight;
    locationCard.querySelector('.card').style.height = `${areaCardHeight}px`;

}

// Function to delete a property
function delete_property(propertyId) {

    const csrftoken = getCookie('csrftoken');

    fetch(`/properties/${propertyId}`, {
        method: 'DELETE',
        headers: {
            'X-CSRFToken': csrftoken
        }
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        } else {
            throw new Error('Property deletion failed');
        }
    })
    .then(data => {
        // Show success modal or message
        const successModal = new bootstrap.Modal(document.getElementById('successModal'));
        successModal.show();
        
        // Edit success modal message
        document.querySelector('#successModal .modal-body').textContent = data.message;
        document.querySelector('#successModal a').style.display = 'none';
    })
    .catch(error => {
        console.error('Error:', error);
    });
}
