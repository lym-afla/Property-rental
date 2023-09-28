document.addEventListener('DOMContentLoaded', function() {

    // Handle New entry buttons in the navbar
    const actionButtons = document.querySelectorAll('.new-entry-button');
    actionButtons.forEach(button => {
        button.addEventListener('click', entryClickHandler);
    });
    
});

// Define a variable to track whether the form has been fetched
let formFetched = {
    'property': false,
    'tenant': false,
    'transaction': false,
}

function entryClickHandler(event) {
    event.preventDefault();

    // Check if new or existing entry is dealt with
    let action = 'undefined';
    if (event.target.classList.contains('new-entry-button')) {
        action = 'new';
    } else if (event.target.classList.contains('edit-entry-button')) {
        action = 'edit';
    }

    console.log(action);

    // Defining the type of entry
    const type = event.target.getAttribute(`data-${action}-type`);
    console.log(type);

    // If the form has already been fetched, show the modal and return
    if (!formFetched[type]) {
        
        getForm(action, type);
        
        // console.log(`Fetching ${type} form`);

        // const divModal = document.getElementById(`${type}ModalDiv`);
        
        // // Fetch the form content
        // fetch(`/properties/new-form/${type}`)
        // .then(response => response.text())
        // .then(formHTML => {
        //     // Inject the form content into the modal body
        //     divModal.innerHTML = formHTML;
            
        //     const modal = new bootstrap.Modal(document.getElementById(`${type}Modal`));
        //     modal.show();

        //     // Attach an event listener to the form's submit event
        //     const form = document.querySelector('#createPropertyForm');
        //     form.removeEventListener('submit', submitSaveHandler);
        //     form.removeEventListener('submit', submitEditProperty);
        //     form.addEventListener('submit', submitSaveHandler);

        //     // Update the formFetched variable to indicate that the form has been fetched
        //     formFetched[type] = true;
        // })
        // .catch(error => {
        //     console.error("Error fetching form:", error);
        // });
    } else {
        console.log(`${type} form already fetched`);
        
        // const form = document.querySelector('#createPropertyForm');
        // form.reset();
        // form.removeEventListener('submit', submitSaveHandler);
        // form.removeEventListener('submit', submitEditProperty);
        // form.addEventListener('submit', submitSaveHandler);

        // Attach an event listener to the form's submit event
        attachSubmitEventListener(action, type);

        const modal = new bootstrap.Modal(document.getElementById(`${type}Modal`));
        modal.show();
        if (action === 'edit') {
            preFillPropertyForm();
        }
    }    
}

// Fetches the appropriate form if not fetched previously
function getForm(action, type) {
    console.log(`Fetching ${type} form`);

    const divModal = document.getElementById(`${type}ModalDiv`);
    
    // Fetch the form content
    fetch(`/properties/new-form/${type}`)
    .then(response => response.text())
    .then(formHTML => {
        // Inject the form content into the modal body
        divModal.innerHTML = formHTML;
       
        // Attach an event listener to the form's submit event
        attachSubmitEventListener(action, type);
       
        const modal = new bootstrap.Modal(document.getElementById(`${type}Modal`));
        modal.show();
        if (action === 'edit') {
            preFillPropertyForm();
        }

        // Update the formFetched variable to indicate that the form has been fetched
        formFetched[type] = true;
    })
    .catch(error => {
        console.error("Error fetching form:", error);
    });
}

function attachSubmitEventListener(action, type) {
    
    // Remove previous event listeners
    const form = document.getElementById(`${type}Form`);
    form.removeEventListener('submit', submitSaveHandler);
    form.removeEventListener('submit', submitEditHandler);

    // Define references to handlers
    const handlerFunction = {
        "new": submitSaveHandler,
        "edit": submitEditHandler,
    }

    // Attach handler function
    form.addEventListener('submit', handlerFunction[action]);
}

// Handling save submission
function submitSaveHandler(event) {
    event.preventDefault(); // Prevent the default form submission
    
    console.log("Saving submission");
    
    const formId = event.target.getAttribute("id");
    const type = formId.replace("Form", "");
    save_edit_property(action="save", type); // Call the save_edit_property function    
}

// Handling edit submission
function submitEditHandler(event) {
    event.preventDefault(); // Prevent the default form submission
    
    console.log("Edit submission");
    
    const formId = event.target.getAttribute("id");
    const type = formId.replace("Form", "");
    const propertyId = document.getElementById('deletePropertyButton').getAttribute('data-property-id');
    save_edit_property(action='edit', type, propertyId); // Call the edit_property function    
}

// Saving and editing new property
function save_edit_property(action, type, propertyId) {

    const csrftoken = getCookie('csrftoken');

    const variables = {
        'save': {
            'link': '/properties/',
            'method': 'POST',
            'success_text': 'created',
            'error_text': 'New property creation failed',
        },
        'edit': {
            'link': `/properties/${propertyId}`,
            'method': 'PUT',
            'success_text': 'edited',
            'error_text': 'Property editing failed',
        }
    }

    const form = document.getElementById(`${type}Form`);
    const formData = new FormData(form);

    // Convert formFields to a JSON string
    const jsonData = JSON.stringify(Object.fromEntries(formData.entries()));

    fetch(variables[action].link, {
        method: variables[action].method,
        body: action === 'save' ? formData : jsonData,
        headers: {
            'X-CSRFToken': csrftoken,
            // 'Content-Type': action === 'save' ? 'multipart/form-data' : 'application/json',
        }
    })
    .then(response => {
        if (response.ok) {
            // Close the createPropertyModal
            let modalReference = document.getElementById(`${type}Modal`);
            let formModal = bootstrap.Modal.getInstance(modalReference);
            formModal.hide();

            const successModal = new bootstrap.Modal(document.getElementById('successModal'));
            successModal.show();
            document.querySelector('#successModal .modal-body').textContent = `Property ${variables[action].success_text} successfully`;
            document.querySelector('#successModal a').style.display = 'none';
            form.reset();
        } else {
            throw new Error(variables[action].error_text);
        }
    })
    .catch(error => {
        console.error('Error:', error)
    });
}

// Function to handle success Modal OK button click. The reference to this function is introduced in layout.html directly
function okButtonEventHandler() {
    
    const successModal = document.getElementById('successModal');
    const successText = successModal.querySelector('.modal-body').textContent;

    // Hide the modal
    let successModalInstance = bootstrap.Modal.getInstance(successModal);
    successModalInstance.hide();
    
    if (successText.includes("deleted") || successText.includes("created")) {
        load_property_table();
    } else if (successText.includes("edited")) {
        const propertyId = document.getElementById('deletePropertyButton').getAttribute('data-property-id');
        load_property_details(propertyId);
    }
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
