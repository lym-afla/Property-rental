document.addEventListener('DOMContentLoaded', function() {

    // JavaScript to Fetch and Show the Form
    const newPropertyLink = document.getElementById('newPropertyLink');
    newPropertyLink.addEventListener('click', newPropertyClickHandler);

    
});

// Define a variable to track whether the form has been fetched
let propertyFormFetched = false;

function newPropertyClickHandler(event) {
    event.preventDefault();

    // If the form has already been fetched, show the modal and return
    if (!propertyFormFetched) {
        console.log('Fetching form');

        const createPropertyModal = document.getElementById('PropertyModal');
        
        // Fetch the form content
        fetch("/properties/new-property-form")
        .then(response => response.text())
        .then(formHTML => {
            // Inject the form content into the modal body
            createPropertyModal.innerHTML = formHTML;
            
            const modal = new bootstrap.Modal(document.getElementById('createPropertyModal'));
            modal.show();

            // Attach an event listener to the form's submit event
            const form = document.querySelector('#createPropertyForm');
            // form.addEventListener('submit', submitSaveProperty);

            // Update the formFetched variable to indicate that the form has been fetched
            propertyFormFetched = true;
        })
        .catch(error => {
            console.error("Error fetching form:", error);
        });
    } else {
        console.log('Modal already fetched');
        
        const form = document.querySelector('#createPropertyForm');
        console.log(form);
        form.reset();

        const modal = new bootstrap.Modal(document.getElementById('createPropertyModal'));
        modal.show();
    }

    document.querySelector('.modal-footer .btn-primary').textContent = 'Create property';
    

    // !!! Because of async nature of promise.then the below may be run before the data is fetched in the 'if' above. So, form is not defined 

    console.log(form);
    // Reassign event listeners
    form.removeEventListener('submit', submitSaveProperty);
    form.removeEventListener('submit', submitEditProperty);
    form.addEventListener('submit', submitSaveProperty);
    
}

// Handling save submission
function submitSaveProperty(event) {
    event.preventDefault(); // Prevent the default form submission
    save_edit_property(action='save'); // Call the save_property function    
}

// Saving new property
function save_edit_property(action, propertyId) {

    console.log('Running save_edit_property' + ` ${action} action.`);

    const csrftoken = getCookie('csrftoken');

    const variables = {
        'save': {
            'link': '/properties',
            'method': 'POST',
            'success_text': 'saved',
            'error_text': 'New property creation failed',
        },
        'edit': {
            'link': `/properties/${propertyId}`,
            'method': 'PUT',
            'success_text': 'edited',
            'error_text': 'Property editing failed',
        }
    }

    const form = document.querySelector('#createPropertyForm');
    const formData = new FormData(form);

    // // Collect form field values using FormData
    // const formFields = {};
    // for (const [name, value] of formData.entries()) {
    //     formFields[name] = value;
    // }

    // Convert formFields to a JSON string
    // const jsonData = JSON.stringify(formFields);

    // Convert formFields to a JSON string
    const jsonData = JSON.stringify(Object.fromEntries(formData.entries()));

    fetch(variables[action].link, {
        method: variables[action].method,
        body: action === 'save' ? formData : jsonData,
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': action === 'save'? 'multipart/form-data' : 'application/json',
        }
    })
    .then(response => {
        if (response.status === 201) {
            const successModal = new bootstrap.Modal(document.getElementById('successModal'));
            successModal.show();
            document.querySelector('#successModal .modal-body').textContent = `Property ${variables[action].success_text} successfully`;
            document.querySelector('#successModal a').style.display = 'block';
            form.reset();
        } else {
            throw new Error(variables[action].error_text);
        }
    })
    .catch(error => {
        console.error('Error:', error)
    });
}

// Function to retrieve the CSRF token from cookies
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
