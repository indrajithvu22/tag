document.getElementById('registrationForm').addEventListener('submit', async function(e) {
    e.preventDefault(); // Stop the default form submission

    const form = e.target;
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());

    const messageElement = document.getElementById('message');
    messageElement.classList.add('hidden'); // Hide previous message

    // Simple validation (can be more complex)
    if (!data.name || !data.regNumber) {
        showMessage('Please fill out all fields.', 'error');
        return;
    }

    try {
        const response = await fetch('/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (response.ok) {
            showMessage(result.message, 'success');
            form.reset(); // Clear form on success
        } else {
            showMessage(result.message || 'An unexpected error occurred.', 'error');
        }

    } catch (error) {
        console.error('Submission error:', error);
        showMessage('Could not connect to the server. Please try again.', 'error');
    }
});

function showMessage(text, type) {
    const messageElement = document.getElementById('message');
    messageElement.textContent = text;
    messageElement.className = 'hidden'; // Reset classes
    messageElement.classList.remove('hidden');
    messageElement.classList.add(type);
}