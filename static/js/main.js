function displayMessage() {
    var urlParams = new URLSearchParams(window.location.search);
    var error = urlParams.get('error');
    var success = urlParams.get('success');
    var messageElement = document.getElementById('display_message');
    
    if (error) {
        messageElement.textContent = error;
        messageElement.style.color = 'red';
    } else if (success) {
        messageElement.textContent = success;
        messageElement.style.color = 'green';
    }
}

window.onload = function() {
    displayMessage();
};