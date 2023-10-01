document.addEventListener('DOMContentLoaded', function() {

    // Handle New entry buttons in the navbar
    const actionButtons = document.querySelectorAll('.new-entry-button-dropdown');
    actionButtons.forEach(button => {
        button.addEventListener('click', elementActionClickHandler);
    });
    
});

// Define a variable to track whether the form has been fetched
let formFetched = {
    'property': false,
    'tenant': false,
    'transaction': false,
}

function elementActionClickHandler(event) {
    event.preventDefault();

    // Check if new or existing entry is dealt with
    let action = 'undefined';
    if (event.target.classList.contains('new-entry-button') || event.target.classList.contains('new-entry-button-dropdown')) {
        action = 'new';
    } else if (event.target.classList.contains('edit-entry-button')) {
        action = 'edit';
    }

    console.log(action);

    // Defining the type of entry
    const type = event.target.getAttribute(`data-${action}-type`);

    // If the form has already been fetched, show the modal and return
    if (!formFetched[type]) {
        
        getForm(action, type);
        
    } else {
        console.log(`${type} form already fetched`);
        
        attachSubmitEventListener(action, type);

        const modal = new bootstrap.Modal(document.getElementById(`${type}Modal`));
        modal.show();
        if (action === 'edit') {
            preFillForm(type);
        }
    }    
}

// Fetches the appropriate form if not fetched previously
function getForm(action, type) {
    console.log(`Fetching ${type} form`);

    const divModal = document.getElementById(`${type}ModalDiv`);
    
    // Fetch the form content
    fetch(`/new-form/${type}`)
    .then(response => response.text())
    .then(formHTML => {
        // Inject the form content into the modal body
        divModal.innerHTML = formHTML;
       
        // Attach an event listener to the form's submit event
        attachSubmitEventListener(action, type);
       
        const modal = new bootstrap.Modal(document.getElementById(`${type}Modal`));
        modal.show();
        if (action === 'edit') {
            preFillForm(type);
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
    handle_type('save', type); // Call the save_edit_property function    
}

// Handling edit submission
function submitEditHandler(event) {
    event.preventDefault(); // Prevent the default form submission
    
    console.log("Edit submission");
    
    const formId = event.target.getAttribute("id");
    const type = formId.replace("Form", "");
    const propertyId = document.getElementById('deleteButton').getAttribute(`data-${type}-id`);
    handle_type('edit', type, propertyId); // Call the edit_property function    
}

function handle_type(action, type, elementId) {

    const Type = type.charAt(0).toUpperCase() + type.slice(1);

    const csrftoken = getCookie('csrftoken');

    const variables = {
        'save': {
            'link': `/handling/${type}`,
            'method': 'POST',
            'success_text': 'created',
            'error_text': `New ${type} save failed`,
        },
        'edit': {
            'link': `/handling/${type}/${elementId}`,
            'method': 'PUT',
            'success_text': 'edited',
            'error_text': `${type} editing failed`,
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
            // Close the create[Type]]Modal
            let modalReference = document.getElementById(`${type}Modal`);
            let formModal = bootstrap.Modal.getInstance(modalReference);
            formModal.hide();

            const successModal = new bootstrap.Modal(document.getElementById('successModal'));
            successModal.show();
            
            document.querySelector('#successModal .modal-body').textContent = `${Type} ${variables[action].success_text} successfully`;
            document.querySelector('#successModal a').style.display = 'none';

            document.getElementById('successModal').setAttribute('data-success-type', type);

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
    
    const successDiv = document.getElementById('successModal');
    const successText = successDiv.querySelector('.modal-body').textContent;
    let type = successDiv.getAttribute("data-success-type");

    // Hide the modal
    let successModalInstance = bootstrap.Modal.getInstance(successDiv);
    successModalInstance.hide();
    
    if (successText.includes("deleted") || successText.includes("created")) {
        if (window.location.pathname.includes("properties")) {
            load_table(type);
        } else {
            if (type === 'property') {
                type = 'properties';
            } else {
                type = type + 's';
            }
            window.location.href = `/${type}`;
        }
    } else if (successText.includes("edited")) {
        const elementId = document.getElementById('deleteButton').getAttribute(`data-${type}-id`);
        load_element_details(type, elementId);
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
