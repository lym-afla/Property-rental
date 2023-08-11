
function load_posts(filter, page = 1) {

    // Set the variable for fetch function and appropriate header based on the filter
    let url = '';
    let header;
    
    if (filter === 'all-posts') {
        header = 'All Posts';
    } else if (filter === 'following') {
        header = 'Following';
    }

    if (filter === 'all-posts' || filter === 'following') {
        
        // Show the mailbox and hide other views
        document.querySelector('#posts-view').style.display = 'block';
        document.querySelector('#new-post-view').style.display = 'none';

        url = `posts/${filter}?page=${page}`;
        document.querySelector('#posts-view h2').textContent = header;
    
    } else if (filter === 'profile') {
        const profileUsername = document.querySelector('#user-profile-container').dataset.username;
        url = `/profile/${profileUsername}/posts?page=${page}`;
    } else {
        throw new Error('Invalid section filter');
    };

    fetch(url)
    .then(response => response.json())
    .then(data => {
        const posts = data.posts;
        const hasNextPage = data.has_next_page;
        const hasPreviousPage = data.has_previous_page;
        document.querySelectorAll('.post').forEach(postElement => postElement.remove());
        posts.forEach(post => {

            const postDiv = document.createElement('div');
            postDiv.classList.add('post');

            let postUsername;

            if (filter !== 'profile') {
                postUsername = document.createElement('h4');
                const postUserLink = document.createElement('a');
                postUserLink.href = `/profile/${post.username}`;
                postUserLink.textContent = post.username;
                postUsername.appendChild(postUserLink);
            }

            const postContent = document.createElement('div');
            postContent.textContent = post.content;
            postContent.classList.add('post-content');

            let editLink;

            if (post.is_author) {
                editLink = document.createElement('a');
                editLink.classList.add('edit-link');
                editLink.href = '#';
                editLink.textContent = 'Edit';
                editLink.dataset.post_id = post.id;
            }

            const postTimestamp = document.createElement('div');
            postTimestamp.classList.add('timestamp');
            postTimestamp.textContent = post.timestamp;

            const postLikes = document.createElement('div');
            postLikes.classList.add('likes');
            const likesIcon = document.createElement('img');
            likesIcon.src = post.liked ? likedIconURL : notLikedIconURL;
            likesIcon.alt = 'Likes';
            likesIcon.width = '20';
            likesIcon.height = '20';
            likesIcon.style.marginRight = '5px';
            post.likesIcon = likesIcon;
            const likesCount = document.createElement('span');
            likesCount.textContent = post.likes_count;
            post.likesCount = likesCount;
            postLikes.appendChild(likesIcon);
            postLikes.appendChild(likesCount);
            likesIcon.addEventListener('click', () => like(post));
            

            if (postUsername) {
                postDiv.appendChild(postUsername);
            }
            if (editLink) {
                postDiv.appendChild(editLink);
            }
            postDiv.appendChild(postContent);
            postDiv.appendChild(postTimestamp);
            postDiv.appendChild(postLikes);

            document.querySelector('.posts-container').appendChild(postDiv);
        });
        renderPagination(hasNextPage, hasPreviousPage, filter, page);
        attachEditLinkEventListeners();
    })
    .catch(error => {
        console.log(error);
    });
}

function renderPagination(hasNextPage, hasPreviousPage, filter, currentPage) {

    const paginationContainer = document.querySelector('.pagination');
    paginationContainer.innerHTML = '';

    const liElement = document.createElement('li');
    liElement.classList.add('page-item');

    if (hasPreviousPage) {
        const previousLinkElement = document.createElement('a');
        previousLinkElement.classList.add('page-link');
        previousLinkElement.href = '#';
        previousLinkElement.textContent = 'Previous';
        previousLinkElement.addEventListener('click', () => {
            load_posts(filter, currentPage - 1);
        });
        liElement.appendChild(previousLinkElement);
    }

    if (hasNextPage) {
        const NextLinkElement = document.createElement('a');
        NextLinkElement.classList.add('page-link');
        NextLinkElement.href = '#';
        NextLinkElement.textContent = 'Next';
        NextLinkElement.addEventListener('click', () => {
            load_posts(filter, currentPage + 1);
        });
        liElement.appendChild(NextLinkElement);
    }

    paginationContainer.appendChild(liElement);

}

function editPost(post_id, postContent) {
    
    postContent.parentElement.querySelector('.edit-link').style.display = 'none';

    const postTextArea = document.createElement('textarea');
    postTextArea.classList.add('form-control', 'mb-2');
    postTextArea.value = postContent.textContent;
    postContent.replaceWith(postTextArea);

    postTextArea.focus(); // Set focus on the textarea

    const saveButton = document.createElement('button');
    saveButton.textContent = 'Save';
    saveButton.classList.add('btn', 'btn-primary', 'mr-2');
    const cancelButton = document.createElement('button');
    cancelButton.textContent = 'Cancel';
    cancelButton.classList.add('btn', 'btn-secondary');

    saveButton.addEventListener('click', () => {
        saveEditedPost(post_id, postTextArea);
    });

    cancelButton.addEventListener('click', () => {
        cancelEditedPost(postTextArea);
    });

    const postDiv = postTextArea.parentElement;
    postDiv.insertBefore(saveButton, postDiv.children[3]);
    postDiv.insertBefore(cancelButton, postDiv.children[4]);
}

function saveEditedPost(post_id, postTextArea) {

    const newContent = postTextArea.value;

    fetch(`/posts/${post_id}/edit`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({content: newContent})
    })
    .then(response => {
        if (response.ok) {
            const postContent = document.createElement('div');
            postContent.textContent = postTextArea.value;
            postContent.classList.add('post-content');
            postTextArea.replaceWith(postContent);

            document.querySelectorAll('.post .btn').forEach(button => {
                button.remove();
            });

            postContent.parentElement.querySelector('.edit-link').style.display = 'block';    
        } else {
            console.log('Error occured during update');
        }
    }) 
    .catch(erorr => {
        console.log(error);
    });
}

// Cancel editing
function cancelEditedPost(postTextArea) {

    const postContent = document.createElement('div');
    postContent.textContent = postTextArea.value;
    postContent.classList.add('post-content');
    postTextArea.replaceWith(postContent);

    // Delete Save and Cancel buttons
    postContent.parentElement.querySelectorAll('.post .btn').forEach(button => {
        button.remove();
    });

    postContent.parentElement.querySelector('.edit-link').style.display = 'block';

}

function attachEditLinkEventListeners() {
    const editLinks = document.querySelectorAll('.edit-link');
    editLinks.forEach(editLink => {
        editLink.addEventListener('click', (event) => {
            event.preventDefault();
            const post_id = editLink.dataset.post_id;
            const postContent = editLink.parentElement.querySelector('.post-content');
            editPost(post_id, postContent);
        });
    });
}

function like(post) {

    fetch(`/posts/${post.id}/like`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({like: !post.liked})
    })
    .then(response => {
        if (response.ok) {
            let likesIcon = post.likesIcon;
            let likesCount = post.likesCount;
            
            // Update the likes icon image source
            likesIcon.src = post.liked ? notLikedIconURL : likedIconURL;

            if (post.liked) {
                post.likes_count -= 1;    
            } else {
                post.likes_count += 1;
            }

            likesCount.textContent = post.likes_count;

            // Toggle like status
            post.liked = !post.liked;

        } else {
            console.log('Error occured during the update.')
        }
    })
    .catch(error => {
        console.log(error)
    })
}
