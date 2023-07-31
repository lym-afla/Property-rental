
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