document.addEventListener('DOMContentLoaded', function() {

  // Use buttons to toggle between views
  document.querySelector('#inbox').addEventListener('click', () => load_mailbox('inbox'));
  document.querySelector('#sent').addEventListener('click', () => load_mailbox('sent'));
  document.querySelector('#archived').addEventListener('click', () => load_mailbox('archive'));
  document.querySelector('#compose').addEventListener('click', () => compose_email(null));

  // By default, load the inbox
  load_mailbox('inbox');
});

function compose_email(email) {

  // Show compose view and hide other views
  document.querySelector('#emails-view').style.display = 'none';
  document.querySelector('#compose-view').style.display = 'block';
  document.querySelector('#email-view').style.display = 'none';

  if (email === null) {
    recipients = '';
    subject = '';
    body = '';
  } else {
    recipients = email.sender;
    subject = email.subject.startsWith('Re: ') ? email.subject : `Re: ${email.subject}`;
    body = '\n\n' + `On ${email.timestamp} ${email.sender} wrote:` + '\n' + email.body;
  }

  document.querySelector('#compose-recipients').value = recipients;
  document.querySelector('#compose-subject').value = subject;
  document.querySelector('#compose-body').value = body;

  document.querySelector('form').onsubmit = () => {
    
    fetch('/emails', {
      method: 'POST',
      body: JSON.stringify({
        recipients: document.querySelector('#compose-recipients').value,
        subject: document.querySelector('#compose-subject').value,
        body: document.querySelector('#compose-body').value
      })
    })
    .then(response => {
      if (response.ok && response.status == 201) {
        return response.json();
      } else {
        return response.json().then(data => {
          throw new Error(data.error);
        });
      }
    })
    .then(data => {
      console.log(data.message);
      load_mailbox('sent');  
    })
    .catch(error => {
      console.log(error)
      alert(error.message);
    })
    return false;
  };
}

function load_mailbox(mailbox) {
  
  // Show the mailbox and hide other views
  document.querySelector('#emails-view').style.display = 'block';
  document.querySelector('#compose-view').style.display = 'none';
  document.querySelector('#email-view').style.display = 'none';

  // Show the mailbox name
  document.querySelector('#emails-view').innerHTML = `<h3>${mailbox.charAt(0).toUpperCase() + mailbox.slice(1)}</h3>`;

  // Show the list of emails
  fetch(`/emails/${mailbox}`)
  .then(response => response.json())
  .then(emails => {
    // console.log(emails);
    emails.forEach(email => {
      const emailDiv = document.createElement('div');
      emailDiv.classList.add('email-box');

      const senderSpan = document.createElement('span');
      senderSpan.textContent = email.sender;
      senderSpan.style.fontWeight = 'bold';

      const subjectSpan = document.createElement('span');
      subjectSpan.textContent = email.subject;
      subjectSpan.style.marginLeft = '10px';
      
      const timestampSpan = document.createElement('span');
      timestampSpan.textContent = email.timestamp;
      timestampSpan.classList.add('timestamp');
      timestampSpan.style.color = 'grey';

      emailDiv.appendChild(senderSpan);
      emailDiv.appendChild(subjectSpan);
      emailDiv.appendChild(timestampSpan);

      emailDiv.addEventListener('click', () => load_email(email.id, mailbox));

      if (email.read) {
        emailDiv.style.backgroundColor = 'lightgray';
      } else {
        emailDiv.style.backgroundColor = 'white';
      }

      document.querySelector('#emails-view').appendChild(emailDiv);

    });
  });
}

function load_email(id, mailbox) {

  // Show the email and hide other views
  document.querySelector('#emails-view').style.display = 'none';
  document.querySelector('#compose-view').style.display = 'none';
  document.querySelector('#email-view').style.display = 'block';

  console.log(id);

  fetch(`/emails/${id}`)
  .then(response => {
    if (response.ok) {
      return response.json();
    } else {
      return response.json().then(data => {
        throw new Error(data.error);
      });
    }
  })
  .then(email => {
    const emailView = document.querySelector('#email-view');

    const archiveButton = document.createElement('button');
    archiveButton.classList.add('btn', 'btn-sm', 'btn-outline-primary');

    const replyButton = document.createElement('button');
    replyButton.classList.add('btn', 'btn-sm', 'btn-outline-primary', 'mr-1');
    replyButton.textContent = 'Reply';

    if (mailbox === 'archive') {
      archiveButton.textContent = 'Unarchive';
    } else if (mailbox ==='sent') {
      archiveButton.style.display = 'none';
      replyButton.style.display = 'none';
    } else {
      archiveButton.textContent = 'Archive';
    }

    if (mailbox != 'sent') {
      replyButton.addEventListener('click', () => compose_email(email));
      archiveButton.addEventListener('click', () => archiving(id, email));
    }

    emailView.innerHTML = `
      <div><strong>From:</strong> <span>${email.sender}</span></div>
      <div><strong>To:</strong> <span>${email.recipients}</span></div>
      <div><strong>Subject:</strong> <span>${email.subject}</span></div>
      <div><strong>Timestamp:</strong> <span>${email.timestamp}</span></div>
    `;

    emailView.append(replyButton);
    emailView.append(archiveButton);
    
    emailView.insertAdjacentHTML('beforeend', `
      <hr>
      <div>${email.body.replace(/\n/g, '<br>')}</div>
    `);

    // Marking the email as read
    fetch(`/emails/${id}`, {
      method: 'PUT',
      body: JSON.stringify({
        read: true
      })
    })
    .then(response => {
      if (!response.ok) {
        throw new Error('Could not mark email as read');
      }
    })
    .catch(error => {
      console.log(error);
      alert(error.message);
    });
  })
  .catch(error => {
    console.log(error);
    alert(error.message);
  });
}

function archiving(id, email) {
  fetch(`/emails/${id}`, {
    method: 'PUT',
    body: JSON.stringify({
      archived: !email.archived
    })
  })
  .then(response => {
    if (response.ok) {
      load_mailbox('inbox');
    } else {
      throw new Error('Could not mark email as (un)archived');
    }
  })
  .catch(error => {
    console.log(error);
    alert(error.message);
  });
}
