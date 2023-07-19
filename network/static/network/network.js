document.addEventListener('DOMContentLoaded', () => {
    // Use buttons to toggle between views
    document.querySelector('#new-post').addEventListener('click', () => new_post());
  
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

}
