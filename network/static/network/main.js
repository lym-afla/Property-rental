document.addEventListener('DOMContentLoaded', () => {
    // Add event listeners for New post button to work, but only if it exists (it does not exist when user is not logged in)
    if (document.querySelector('#new-post-button')) {
        document.querySelector('#new-post-button').addEventListener('click', () => new_post());
    }

    // By default, load list of posts
    load_posts();
});

function load_posts() {

    // Show the mailbox and hide other views
    document.querySelector('#posts-view').style.display = 'block';
    document.querySelector('#new-post-view').style.display = 'none';

}

function new_post() {

    // Show the mailbox and hide other views
    document.querySelector('#posts-view').style.display = 'none';
    document.querySelector('#new-post-view').style.display = 'block';

    document.querySelector('#new-post-form').onsubmit = () => {
        fetch('/posts', {
            method: 'POST',
            body: JSON.stringify({
                content: document.querySelector('#new-post-text').value
            })
        })
        .then(response => {
            if (response.ok && response.status === 201) {
                return response.json();
            } else {
                return response.json().then(data => {
                    throw new Error(data.error);
                });
            }
        })
        .then(data => load_posts())
        .catch(error => {
            console.log(error);
        })
    }

}
