document.addEventListener('DOMContentLoaded', () => {

    // Calculate the margin from the top of the mt-4 container class in the posts-view div
    const containerMargin = document.querySelector('.container-fluid').offsetTop;
    // Set the height of the container-fluid to the remaining height after subtracting the navbar height and mt-4 height
    document.querySelector('.container-fluid').style.height = `calc(100vh - ${containerMargin}px)`;

    // Handling following/unfollowing functionality
    const followForm = document.querySelector('#follow-form');
    const followButton = document.querySelector('#follow-button');
    const profileUsername = document.querySelector('#user-profile-container').dataset.username;
    console.log(profileUsername);

    if (followForm) {
        followForm.addEventListener('submit', (event) => {
            event.preventDefault(); // Prevent the default form submission behavior

            const formData = new FormData(followForm);
            const csrfToken = formData.get("csrfmiddlewaretoken");

            fetch(`/profile/${profileUsername}/follow/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                },
                body: formData
            })
            .then((response) => {
                if (response.ok) {
                    return response.json()
                } else {
                    throw new Error("Network response was not ok")
                }
            })
            .then((data) => {
                if (data.is_following) {
                    followButton.textContent = 'Unfollow';
                } else {
                    followButton.textContent = 'Follow';
                };
                // Update the followers count
                document.getElementById('profile-followers').textContent = data.followers_count;
            })
            .catch((error) => console.error('Error:', error));
        });
    }
});
