
document.addEventListener('DOMContentLoaded', function () {
    document.getElementById('userSettingsForm').addEventListener('submit', function (event) {
        event.preventDefault();

        const form = event.target;
        const formData = new FormData(form);

        fetch(form.action, {
            method: 'POST',
            body: formData,
        })
            .then(response => {
                return response.json();
            })
            .then(data => {
                const successModal = new bootstrap.Modal(document.getElementById('successModal'));
                if (data.success) {
                    // Clear existing error messages
                    const errorElements = document.querySelectorAll('.form-error');
                    errorElements.forEach(element => {
                        element.style.display = 'none'; // Hide all error messages
                    });
                    
                    document.querySelector('#successModal .modal-body').textContent = "User settings saved successfully";
                    document.querySelector('#successModal a').style.display = 'none';
                    document.querySelector('#successModal h5').textContent = 'Success';
                    document.getElementById('successModal').setAttribute('data-success-type', "user-settings");
                    successModal.show();
                } else if (data.errors) {
                    handleFormErrors(data.errors);
                    throw new Error("Failed to save settings. Please try again.");
                }
            })
            .catch(error => {
                console.error('Error:', error);
            });
    });
});

function handleFormErrors(errors) {
    // Clear existing error messages
    const errorElements = document.querySelectorAll('.form-error');
    errorElements.forEach(element => {
        element.style.display = 'none'; // Hide all error messages
    });

    // Display error messages next to the corresponding form fields
    Object.keys(errors).forEach(fieldName => {
        const errorField = document.getElementById('id_' + fieldName + '_error');
        if (errorField) {
            errorField.textContent = errors[fieldName].join(', ');
            errorField.style.display = 'block'; // Show the error message
        }
    });
}


// document.addEventListener('DOMContentLoaded', function() {
//     document.getElementById('userSettingsForm').addEventListener('submit', function(event) {
//         event.preventDefault();

//         const form = event.target;
//         const formData = new FormData(form);

//         fetch(form.action, {
//             method: 'POST',
//             body: formData,
//         })
//         .then(response => {
//             const successModal = new bootstrap.Modal(document.getElementById('successModal'));
//             if (response.ok) {
                
                
                
//                 document.querySelector('#successModal .modal-body').textContent = "User settings saved successfully";
                
//             } else {
//                 // console.log(response.json())
//                 // document.querySelector('#successModal .modal-body').textContent = "X";
//                 throw new Error("Failed to save settings. Please try again.");
//             }
//             document.querySelector('#successModal a').style.display = 'none';
//             document.querySelector('#successModal h5').textContent = 'Fail'; 
            

//             document.getElementById('successModal').setAttribute('data-success-type', "user-settings");
//             successModal.show();
//         })
//         .catch(error => {
//             console.error('Error:', error);
//         });

//     });
// });