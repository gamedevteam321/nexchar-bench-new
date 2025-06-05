$(document).ready(function() {
    // Check if chat elements already exist (e.g., due to SPA navigation)
    if ($('#nexchat-floating-button').length > 0) {
        // Potentially re-bind events if needed, or assume they persist
        return;
    }

    // HTML for the chatbox
    const chatHTML = `
        <div id="nexchat-floating-button" title="Chat with Support">
            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather feather-message-square" style="vertical-align: middle;"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
        </div>
        <div id="nexchat-window">
            <div class="nexchat-header">
                <span>NexChat Assistant</span>
                <button class="nexchat-close-btn" title="Close Chat">&times;</button>
            </div>
            <div id="nexchat-messages">
                <div class="nexchat-message bot">Hello! How can I assist you today?</div>
            </div>
            <div id="nexchat-loading-indicator" style="display: none;">Typing...</div>
            <div id="nexchat-error-message" style="display: none;"></div>
            <div class="nexchat-input-area">
                <input type="text" id="nexchat-message-input" placeholder="Type your message...">
                <button id="nexchat-send-button">Send</button>
            </div>
        </div>
    `;

    // Append HTML to the body
    $('body').append(chatHTML);

    // Cache jQuery objects
    const $chatWindow = $('#nexchat-window');
    const $floatingButton = $('#nexchat-floating-button');
    const $messagesContainer = $('#nexchat-messages');
    const $messageInput = $('#nexchat-message-input');
    const $sendButton = $('#nexchat-send-button');
    const $closeButton = $chatWindow.find('.nexchat-close-btn');
    const $loadingIndicator = $('#nexchat-loading-indicator');
    const $errorMessage = $('#nexchat-error-message');

    // --- Event Handlers ---

    // Toggle chat window
    $floatingButton.on('click', function() {
        $chatWindow.toggleClass('open');
        if ($chatWindow.hasClass('open')) {
            $messageInput.focus();
        }
    });

    $closeButton.on('click', function() {
        $chatWindow.removeClass('open');
    });

    // Send message
    $sendButton.on('click', sendMessage);
    $messageInput.on('keypress', function(e) {
        if (e.which === 13 && !e.shiftKey) { // Enter key pressed
            e.preventDefault();
            sendMessage();
        }
    });

    function sendMessage() {
        const messageText = $messageInput.val().trim();
        if (!messageText) return;

        addMessageToUI(messageText, 'user');
        $messageInput.val('');
        $loadingIndicator.show();
        $errorMessage.hide();

        frappe.call({
            method: 'nexchat.api.send_message_to_n8n',
            args: {
                message_text: messageText
            },
            callback: function(r) {
                $loadingIndicator.hide();
                if (r.message && r.message.reply) {
                    addMessageToUI(r.message.reply, 'bot');
                } else if (r.message && r.message.error) {
                    addMessageToUI("Error: " + r.message.error, 'bot', true);
                    $errorMessage.text("Error: " + r.message.error).show();
                } else if (r.exc) {
                    let errorMsg = "An unexpected error occurred. See console for details.";
                    try {
                        const exc_obj = JSON.parse(r.exc);
                        if (exc_obj[0] && exc_obj[0].includes("N8N_WEBHOOK_URL not configured")) {
                            errorMsg = "Chat service is not configured. Please contact administrator.";
                        }
                    } catch(e){}
                    addMessageToUI(errorMsg, 'bot', true);
                    $errorMessage.text(errorMsg).show();
                    console.error("Nexchat Error:", r.exc);
                } else {
                    addMessageToUI('Sorry, I could not process your request.', 'bot', true);
                    $errorMessage.text('Sorry, I could not process your request.').show();
                }
            },
            error: function(r) {
                $loadingIndicator.hide();
                addMessageToUI('Error connecting to server. Please try again.', 'bot', true);
                $errorMessage.text('Error connecting to server. Please try again.').show();
                console.error("Nexchat AJAX Error:", r);
            }
        });
    }

    function addMessageToUI(text, type, isError = false) {
        const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const messageClass = type === 'user' ? 'user' : 'bot';
        const $messageDiv = $(`
            <div class="nexchat-message ${messageClass}">
                ${frappe.utils.escape_html(text)}
                <span class="timestamp">${timestamp}</span>
            </div>
        `);
        if (isError) {
            $messageDiv.css('background-color', '#f8d7da').css('color', '#721c24');
        }
        $messagesContainer.append($messageDiv);
        $messagesContainer.scrollTop($messagesContainer[0].scrollHeight); // Scroll to bottom
    }
}); 