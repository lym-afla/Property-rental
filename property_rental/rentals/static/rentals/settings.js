document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('userSettingsForm').addEventListener('submit', function(event) {
        event.preventDefault();

        const form = event.target;
        const formData = new FormData(form);

        fetch(form.action, {
            method: 'POST',
            body: formData,
        })
        .then(response => {
            if (response.ok) {
                const successModal = new bootstrap.Modal(document.getElementById('successModal'));
                successModal.show();
                
                document.querySelector('#successModal .modal-body').textContent = "User settings saved successfully";
                document.querySelector('#successModal a').style.display = 'none';

                document.getElementById('successModal').setAttribute('data-success-type', "user-settings");
            } else {
                throw new Error("Failed to save settings. Please try again.");
            }
        })
        .catch(error => {
            console.error('Error:', error);
        });

    });
});