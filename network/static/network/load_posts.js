function load_posts(filter, page = 1) {

    // Set the variable for fetch function and appropriate header based on the filter
    let url = '';
    let header;
    
    if (filter === 'all-posts' || filter === 'following') {
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

            if (postUsername) {
                postDiv.appendChild(postUsername);
            }
            postDiv.appendChild(postContent);
            postDiv.appendChild(postTimestamp);
            postDiv.appendChild(postLikes);

            document.querySelector('.posts-container').appendChild(postDiv);
        });
        renderPagination(hasNextPage, hasPreviousPage, filter, page);
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