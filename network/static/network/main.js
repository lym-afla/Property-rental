
document.addEventListener('DOMContentLoaded', () => {
    // Add event listeners for New post button to work, but only if it exists (it does not exist when user is not logged in)
    if (document.querySelector('#new-post-button')) {
        document.querySelector('#new-post-button').addEventListener('click', function() {
            
            const section = 'new-post';

            // history.pushState({section: section}, "", '?section=new-post');
            new_post();
        });
    };

    if (document.querySelector('#following-button')) {
        document.querySelector('#following-button').addEventListener('click', function() {
            
            const section = 'following';
           
            // history.pushState({section: section}, "", '?section=following');            
            load_posts('following');
        });
    };

    document.querySelector('#all-posts-button').addEventListener('click', function() {
        
        const section = 'all-posts';

        // history.push State({section: section}, "", '?section=all-posts');
        load_posts('all-posts');
    });

    console.log(section);
    if (section === 'new-post') {
        new_post();
    } else {
        load_posts(section);
    }

    // Adding event listener for the popstate event
    // window.addEventListener('popstate', function(event) {
    //     if (event.state) {
    //         const previousSection = event.state?.section;
    //         if (previousSection === 'following') {
    //             load_posts('following');
    //         } else if (previousSection === 'new-post') {
    //             new_post();
    //         } else if (previousSection === 'all-posts') {
    //             load_posts('all');
    //         }
    //     } else {
    //         history.back();
    //     }
    // });
});

// function load_posts(filter, page = 1) {

//     // Show the mailbox and hide other views
//     document.querySelector('#posts-view').style.display = 'block';
//     document.querySelector('#new-post-view').style.display = 'none';

//     // Set the variable for fetch function and appropriate header based on the filter
//     let url = '';
//     if (filter === 'all-posts') {
//         url = `posts/${filter}?page=${page}`;
//         document.querySelector('#posts-view h2').textContent = 'All Posts';
//     } else if (filter === 'following') {
//         url = `posts/${filter}?page=${page}`;
//         document.querySelector('#posts-view h2').textContent = 'Following';
//     } else if (filter === 'profile') {
//         const profileUsername = document.querySelector('#user-profile-container').dataset.username;
//         url = `/profile/${profileUsername}?page=${page}`;
//     } else {
//         throw new Error('Invalid section filter');
//     };

//     fetch(url)
//     .then(response => response.json())
//     .then(data => {
//         const posts = data.posts;
//         const hasNextPage = data.has_next_page;
//         const hasPreviousPage = data.has_previous_page;
//         document.querySelectorAll('.post').forEach(postElement => postElement.remove());
//         posts.forEach(post => {
//             const postDiv = document.createElement('div');
//             postDiv.classList.add('post');

//             if (filter != 'profile') {
//                 const postUsername = document.createElement('h4');
//                 const postUserLink = document.createElement('a');
//                 postUserLink.href = `/profile/${post.username}`;
//                 postUserLink.textContent = post.username;
//                 postUsername.appendChild(postUserLink);
//             };

//             const postContent = document.createElement('div');
//             postContent.textContent = post.content;

//             const postTimestamp = document.createElement('div');
//             postTimestamp.classList.add('timestamp');
//             postTimestamp.textContent = post.timestamp;

//             const postLikes = document.createElement('div');
//             postLikes.classList.add('likes');
//             const likesIcon = document.createElement('img');
//             likesIcon.src = likesIconURL;
//             likesIcon.alt = 'Likes';
//             likesIcon.width = '20';
//             likesIcon.height = '20';
//             likesIcon.style.marginRight = '5px';
//             const likesCount = document.createElement('span');
//             likesCount.textContent = post.likes_count;
//             postLikes.appendChild(likesIcon);
//             postLikes.appendChild(likesCount);

//             if (filter != 'profile') { postDiv.appendChild(postUsername); };
//             postDiv.appendChild(postContent);
//             postDiv.appendChild(postTimestamp);
//             postDiv.appendChild(postLikes);

//             document.querySelector('.posts-container').appendChild(postDiv);
//         });
//         renderPagination(hasNextPage, hasPreviousPage, filter, page);
//     })
//     .catch(error => {
//         console.log(error);
//     });
// }

// function renderPagination(hasNextPage, hasPreviousPage, filter, currentPage) {

//     const paginationContainer = document.querySelector('.pagination');
//     paginationContainer.innerHTML = '';

//     const liElement = document.createElement('li');
//     liElement.classList.add('page-item');

//     if (hasPreviousPage) {
//         const previousLinkElement = document.createElement('a');
//         previousLinkElement.classList.add('page-link');
//         previousLinkElement.href = '#';
//         previousLinkElement.textContent = 'Previous';
//         previousLinkElement.addEventListener('click', () => {
//             load_posts(filter, currentPage - 1);
//         });
//         liElement.appendChild(previousLinkElement);
//     }

//     if (hasNextPage) {
//         const NextLinkElement = document.createElement('a');
//         NextLinkElement.classList.add('page-link');
//         NextLinkElement.href = '#';
//         NextLinkElement.textContent = 'Next';
//         NextLinkElement.addEventListener('click', () => {
//             load_posts(filter, currentPage + 1);
//         });
//         liElement.appendChild(NextLinkElement);
//     }

//     paginationContainer.appendChild(liElement);

// }

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