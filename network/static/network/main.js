document.addEventListener('DOMContentLoaded', () => {
    // Add event listeners for New post button to work, but only if it exists (it does not exist when user is not logged in)
    if (document.querySelector('#new-post-button')) {
        document.querySelector('#new-post-button').addEventListener('click', () => new_post());
    };

    if (document.querySelector('#following-button')) {
        document.querySelector('#following-button').addEventListener('click', () => load_posts('following'));
    };

    document.querySelector('#all-posts-button').addEventListener('click', () => load_posts('all'));

    // By default, load list of posts
    // load_posts('all');

    // Create follow/unfollow functionality
    const followForm = document.querySelector('#follow-form');
    if (followForm) {
        followForm.addEventListener('submit', followFunction);
    };
    
    // Fix the height of posts container on Profile page
    const containerMargin = document.querySelector('.container-fluid').offsetTop;
    if (containerMargin) {
        // Set the height of the container-fluid to the remaining height after subtracting the navbar height
        document.querySelector('.container-fluid').style.height = `calc(100vh - ${containerMargin}px)`;
    };

});

function load_posts(filter) {

    // Show the mailbox and hide other views
    document.querySelector('#posts-view').style.display = 'block';
    document.querySelector('#new-post-view').style.display = 'none';

    // Set the appropriate header based on the filter
    if (filter === 'all') {
        document.querySelector('#posts-view h2').textContent = 'All Posts';
    } else if (filter === 'following') {
        document.querySelector('#posts-view h2').textContent = 'Posts from users following';
    } else {
        throw new Error('Invalid filter');
    }

    fetch(`posts/${filter}`)
    .then(response => response.json())
    .then(posts => {
        document.querySelectorAll('.post').forEach(postElement => postElement.remove());
        posts.forEach(post => {
            console.log(post);
            const postDiv = document.createElement('div');
            postDiv.classList.add('post');

            const postUsername = document.createElement('h4');
            const postUserLink = document.createElement('a');
            postUserLink.href = `/profile/${post.username}`;
            postUserLink.textContent = post.username;
            postUsername.appendChild(postUserLink);

            const postContent = document.createElement('div');
            postContent.textContent = post.content;

            const postTimestamp = document.createElement('div');
            postTimestamp.classList.add('timestamp');
            postTimestamp.textContent = post.timestamp;

            const postLikes = document.createElement('div');
            postLikes.classList.add('likes');
            const likesIcon = document.createElement('img');
            likesIcon.src = likesIconURL;
            likesIcon.alt = 'Likes';
            likesIcon.width = '20';
            likesIcon.height = '20';
            likesIcon.style.marginRight = '5px';
            const likesCount = document.createElement('span');
            likesCount.textContent = post.likes_count;
            postLikes.appendChild(likesIcon);
            postLikes.appendChild(likesCount);

            postDiv.appendChild(postUsername);
            postDiv.appendChild(postContent);
            postDiv.appendChild(postTimestamp);
            postDiv.appendChild(postLikes);

            document.querySelector('#posts-view').appendChild(postDiv);
        });
    });
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

function followFunction(event) {
    const followButton = document.querySelector('#follow-button');
    const profileUsername = document.querySelector('#user-profile-container').dataset.username;
    
    event.preventDefault(); // Prevent the default form submission behavior

    const formData = new FormData(document.querySelector('#follow-form'));
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
}