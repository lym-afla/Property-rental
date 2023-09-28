document.addEventListener('DOMContentLoaded', function() {

    // Get the current URL path
    const path = window.location.pathname;
        
    // Extract the type from the path
    const match = path.match(/^\/(properties|tenants|transactions)\/?/);
    const type = match ? match[1] : null;

    // Hide details container
    document.getElementById(`${type}DetailsContainer`).style.display = 'none';

    // By default, load the corresponding table
    load_table(type);

    // Add event listener to the "New [Type]" button
    const newTypeButton = document.querySelector('.newTypeButton');
    newTypeButton.addEventListener('click', entryClickHandler);

});

function load_table(type) {

    const Type = type.charAt(0).toUpperCase() + type.slice(1);

    // Show the [type] table and hide other views
    document.getElementById(`${type}sTable`).style.display = 'block';
    document.querySelector('.newTypeButton').style.display = 'block';
    document.getElementById(`${type}DetailsContainer`).style.display = 'none';
    
    // Delete event listeners from the buttons on detailed [Type] page
    const detailElementCheck = document.getElementById(`backTo${Type}`);
    if (detailElementCheck) {
        document.getElementById('confirmDeleteButton').removeEventListener('click', deleteElementHandler);
        document.getElementById(`backTo${Type}`).removeEventListener('click', backToPropertiesClickHandler);
        document.getElementById(`edit${Type}Button`).removeEventListener('click', editClickHandler);
        detailElementCheck.parentElement.remove();
    }
    
    // Show the page name
    document.querySelector('h2').innerHTML = `${Type}s`;

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
            row.className = 'propertyRow';
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
            break;
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

    const type = event.target.classList.replace("Name", "");

    // Get the property ID from the data attribute
    const elementId = this.closest('.propertyRow').getAttribute(`data-${type}-id`);

    load_element_details(elementId);
}

// Delete click handler
function deleteElementHandler(event) {

    event.preventDefault();

    // Extract what type of element is being dealt with
    const type = event.target.getAttribute("data-delete-type");
    
    // Get element ID from delete button
    const elementId = event.target.getAttribute(`data-${type}-id`);
    
    const csrftoken = getCookie('csrftoken');

    fetch(`/properties/${elementId}`, {
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

function load_element_details(elementId) {
    // to be created
}