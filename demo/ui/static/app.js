// Global state
let allMessages = [];
let protectedMode = true;
let knownIdentities = new Set(['Alice', 'Bob', 'Charlie']);
let aclUsers = [];
let aclGroups = [];

// Initialize app on load
document.addEventListener('DOMContentLoaded', async () => {
    await loadIdentities();
    await refreshAll();
    updateModeDisplay();
    await loadACLData();

    // Setup enter key to send
    document.getElementById('message-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
});

// Load and populate identity list
function loadIdentities() {
    const select = document.getElementById('current-identity');
    const currentValue = select.value;

    select.innerHTML = '<option value="">Select or type below...</option>';

    knownIdentities.forEach(identity => {
        const option = document.createElement('option');
        option.value = identity;
        option.textContent = identity;
        select.appendChild(option);
    });

    // Restore previous selection or set default
    if (currentValue && knownIdentities.has(currentValue)) {
        select.value = currentValue;
    } else if (knownIdentities.has('Alice')) {
        select.value = 'Alice';
    }
}

// Update protection mode display
function updateModeDisplay() {
    const modeLabel = document.getElementById('mode-label');
    const checkbox = document.getElementById('protected-mode');

    protectedMode = checkbox.checked;

    if (protectedMode) {
        modeLabel.textContent = 'PROTECTED MODE';
        modeLabel.className = 'mode-label protected';
    } else {
        modeLabel.textContent = 'NAÏVE MODE ⚠️';
        modeLabel.className = 'mode-label naive';
    }
}

// Toggle full info section
function toggleFullInfo() {
    const checkbox = document.getElementById('show-full-info');
    const content = document.getElementById('full-info-content');

    if (checkbox.checked) {
        content.style.display = 'grid';
        loadProjectionDebug();
    } else {
        content.style.display = 'none';
    }
}

// Send message
async function sendMessage() {
    const input = document.getElementById('message-input');
    const identitySelect = document.getElementById('current-identity');
    const customIdentityInput = document.getElementById('custom-identity');

    const content = input.value.trim();

    // Get identity from custom input first, then from select
    let identity = customIdentityInput.value.trim();
    if (!identity) {
        identity = identitySelect.value.trim();
    }

    if (!content) {
        alert('Please enter a message');
        return;
    }

    if (!identity) {
        alert('Please select or enter an identity name');
        return;
    }

    // Add identity to known list if new
    if (!knownIdentities.has(identity)) {
        knownIdentities.add(identity);
        loadIdentities();
    }

    // Clear custom input and select the identity in dropdown
    customIdentityInput.value = '';
    identitySelect.value = identity;

    // Check if message is for assistant
    if (content.includes('@assistant')) {
        await sendToAssistant(identity, content);
    } else {
        await postUserMessage(identity, content);
    }

    // Clear input
    input.value = '';
}

// Post user message
async function postUserMessage(author, content) {
    try {
        await apiCall('/messages', 'POST', { author, content });
        await refreshAll();
    } catch (error) {
        console.error('Failed to post message:', error);
    }
}

// Send message to assistant
async function sendToAssistant(principal, rawContent) {
    // Extract the actual query (remove @assistant and principal name)
    let query = rawContent.replace(/@assistant/gi, '').trim();

    // Remove principal name if it's at the start of the query
    const principalPrefix = new RegExp(`^${principal}:?\\s*`, 'i');
    query = query.replace(principalPrefix, '').trim();

    if (!query) {
        alert('Please include a question for the assistant');
        return;
    }

    // Show thinking indicator (DON'T post user message yet - it will be added after API call)
    const chatDiv = document.getElementById('chat-messages');
    const thinkingDiv = document.createElement('div');
    thinkingDiv.className = 'chat-message assistant-message';
    thinkingDiv.id = 'thinking-indicator';
    thinkingDiv.innerHTML = `
        <div class="message-header">
            <span class="message-author assistant">Assistant</span>
            <span class="message-time">now</span>
        </div>
        <div class="message-content">Thinking...</div>
    `;
    chatDiv.appendChild(thinkingDiv);

    // Auto-scroll to thinking indicator
    requestAnimationFrame(() => {
        chatDiv.scrollTop = chatDiv.scrollHeight;
    });

    try {
        const result = await apiCall('/assistant/ask', 'POST', {
            principal,
            query,
            protected_mode: protectedMode,
        });

        // Remove thinking indicator
        const thinking = document.getElementById('thinking-indicator');
        if (thinking) thinking.remove();

        // Clean the response - remove various prefixes
        // Only remove principal name if it's clearly a prefix (followed by colon)
        console.log("Raw LLM response:", result.response);
        const responsePrefixPattern = new RegExp(`^${principal}:\\s*`, 'i');
        let cleanResponse = result.response
            .replace(/@assistant/gi, '')
            .replace(responsePrefixPattern, '')  // Only remove "Name: " pattern
            .replace(/^\[.*?\]:\s*/, '')  // Remove [Name]: prefix
            .trim();
        console.log("After cleaning:", cleanResponse);

        // NOW add both user query (ORIGINAL with @assistant) and assistant response to chat
        await apiCall('/messages', 'POST', {
            author: principal,
            content: rawContent,  // Use original message, not cleaned query
        });

        await apiCall('/messages', 'POST', {
            author: 'Assistant',
            content: cleanResponse,
            addressed_to: principal,  // Mark which principal this response is for
        });

        // Update debug info if visible
        if (document.getElementById('show-full-info').checked) {
            displayPromptDebug(result.prompt_debug);
            await loadProjectionDebug();
        }

        await refreshAll();

    } catch (error) {
        // Remove thinking indicator
        const thinking = document.getElementById('thinking-indicator');
        if (thinking) thinking.remove();

        console.error('Assistant error:', error);
        alert(`Error: ${error.message}`);
    }
}

// Load all messages and render chat
async function loadMessages() {
    allMessages = await apiCall('/messages');
    renderChat();
}

// Render chat messages
function renderChat() {
    const chatDiv = document.getElementById('chat-messages');
    const wasAtBottom = chatDiv.scrollHeight - chatDiv.scrollTop <= chatDiv.clientHeight + 50;

    chatDiv.innerHTML = '';

    if (allMessages.length === 0) {
        chatDiv.innerHTML = '<p style="color: #999; text-align: center;">No messages yet</p>';
        return;
    }

    allMessages.forEach(msg => {
        const messageDiv = document.createElement('div');
        const isAssistant = msg.author === 'Assistant';

        messageDiv.className = `chat-message ${isAssistant ? 'assistant-message' : 'user-message'}`;

        const time = new Date(msg.created_at).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit'
        });

        messageDiv.innerHTML = `
            <div class="message-header">
                <span class="message-author ${isAssistant ? 'assistant' : ''}">${escapeHtml(msg.author)}</span>
                <span class="message-time">${time}</span>
            </div>
            <div class="message-content">${escapeHtml(msg.content)}</div>
            ${!isAssistant ? `
                <div class="message-actions">
                    <button onclick="editMessage('${msg.logical_msg_id}')">Edit</button>
                    <button onclick="deleteMessage('${msg.logical_msg_id}')">Delete</button>
                </div>
            ` : ''}
        `;

        chatDiv.appendChild(messageDiv);
    });

    // Auto-scroll to bottom (use requestAnimationFrame for better reliability)
    requestAnimationFrame(() => {
        chatDiv.scrollTop = chatDiv.scrollHeight;
    });
}

// Edit message
async function editMessage(logicalMsgId) {
    const newContent = prompt('Enter new content:');
    if (newContent === null) return;

    const identitySelect = document.getElementById('current-identity');
    const customIdentityInput = document.getElementById('custom-identity');
    const identity = customIdentityInput.value.trim() || identitySelect.value.trim() || 'User';

    try {
        await apiCall(`/messages/${logicalMsgId}`, 'PUT', {
            editor: identity,
            new_content: newContent,
        });
        await refreshAll();
    } catch (error) {
        console.error('Failed to edit message:', error);
    }
}

// Delete message
async function deleteMessage(logicalMsgId) {
    if (!confirm('Delete this message?')) return;

    const identitySelect = document.getElementById('current-identity');
    const customIdentityInput = document.getElementById('custom-identity');
    const identity = customIdentityInput.value.trim() || identitySelect.value.trim() || 'User';

    try {
        await apiCall(`/messages/${logicalMsgId}`, 'DELETE', {
            deleter: identity,
        });
        await refreshAll();
    } catch (error) {
        console.error('Failed to delete message:', error);
    }
}

// Load projection debug info
async function loadProjectionDebug() {
    const identitySelect = document.getElementById('current-identity');
    const customIdentityInput = document.getElementById('custom-identity');
    const identity = customIdentityInput.value.trim() || identitySelect.value.trim();

    if (!identity) return;

    try {
        const projection = await apiCall(`/projection/${identity}`);
        renderProjection(projection);
    } catch (error) {
        console.error('Failed to load projection:', error);
    }
}

// Render projection debug view
function renderProjection(projection) {
    const debugDiv = document.getElementById('projection-debug');

    const controlHtml = projection.effective_control_context.length > 0
        ? projection.effective_control_context.map(msg =>
            `<div class="projection-message">
                <strong>${msg.author}:</strong> ${escapeHtml(msg.content).substring(0, 100)}...
            </div>`
        ).join('')
        : '<p style="color: #999;">No messages from this principal yet</p>';

    const observationHtml = projection.visible_observation_context.length > 0
        ? projection.visible_observation_context.map(msg =>
            `<div class="projection-message">
                <strong>${msg.author}:</strong> ${escapeHtml(msg.content).substring(0, 100)}...
            </div>`
        ).join('')
        : '<p style="color: #999;">No messages from other users</p>';

    debugDiv.innerHTML = `
        <div class="projection-section">
            <h4>Effective Control Context (${projection.effective_control_context.length})</h4>
            <p style="font-size: 0.8em; color: #666; margin-bottom: 8px;">
                Messages that influence the assistant's reply
            </p>
            <div class="projection-messages">${controlHtml}</div>
        </div>

        <div class="projection-section">
            <h4>Visible Observation Context (${projection.visible_observation_context.length})</h4>
            <p style="font-size: 0.8em; color: #666; margin-bottom: 8px;">
                Accessible via retrieval tools
            </p>
            <div class="projection-messages">${observationHtml}</div>
        </div>
    `;
}

// Display prompt debug info
function displayPromptDebug(promptDebug) {
    const promptDiv = document.getElementById('prompt-debug');
    promptDiv.textContent = promptDebug.formatted_display;
}

// Refresh all data
async function refreshAll() {
    await loadMessages();
    await loadACLData();
    if (document.getElementById('show-full-info').checked) {
        await loadProjectionDebug();
    }
    updateStatus();
}

// Update status
async function updateStatus() {
    try {
        const status = await apiCall('/status');
        document.getElementById('status').textContent =
            `${status.message_count} messages | ${status.event_count} events`;
    } catch (error) {
        console.error('Failed to update status:', error);
    }
}

// Reset conversation
async function resetConversation() {
    if (!confirm('Reset the entire conversation? This will delete all messages.')) {
        return;
    }

    try {
        await apiCall('/reset', 'POST');
        await refreshAll();
    } catch (error) {
        console.error('Failed to reset:', error);
    }
}

// API call helper
async function apiCall(endpoint, method = 'GET', body = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
        },
    };

    if (body) {
        options.body = JSON.stringify(body);
    }

    try {
        const response = await fetch(`/api${endpoint}`, options);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
}

// Utility: Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ACL Management Functions

// Load ACL data
async function loadACLData() {
    try {
        const [usersData, groupsData] = await Promise.all([
            apiCall('/acl/users'),
            apiCall('/acl/groups'),
        ]);

        aclUsers = usersData.users;
        aclGroups = groupsData.groups;

        renderACLPanel();
    } catch (error) {
        console.error('Failed to load ACL data:', error);
    }
}

// Render ACL panel
function renderACLPanel() {
    const container = document.getElementById('user-admin-status');
    if (!container) return;

    // Find the admins group
    const adminsGroup = aclGroups.find(g => g.id === 'admins');
    const adminMembers = adminsGroup ? adminsGroup.members : [];

    container.innerHTML = '';

    // Render each user
    aclUsers.forEach(user => {
        const isAdmin = adminMembers.includes(user.id);

        const itemDiv = document.createElement('div');
        itemDiv.className = `user-admin-item ${isAdmin ? 'is-admin' : ''}`;

        itemDiv.innerHTML = `
            <div class="user-info">
                <span class="user-name">${escapeHtml(user.username)}</span>
                ${isAdmin ? '<span class="admin-badge">ADMIN</span>' : ''}
            </div>
            <button
                class="${isAdmin ? 'demote-button' : 'promote-button'}"
                onclick="${isAdmin ? `demoteUser('${user.id}')` : `promoteUser('${user.id}')`}"
            >
                ${isAdmin ? 'Demote' : 'Promote to Admin'}
            </button>
        `;

        container.appendChild(itemDiv);
    });
}

// Promote user to admin
async function promoteUser(userId) {
    try {
        await apiCall(`/acl/groups/admins/members/${userId}`, 'POST');
        await loadACLData();

        // Show feedback
        const user = aclUsers.find(u => u.id === userId);
        if (user) {
            showToast(`${user.username} promoted to Admin! Their messages now influence all users in Protected Mode.`);
        }
    } catch (error) {
        console.error('Failed to promote user:', error);
        alert('Failed to promote user');
    }
}

// Demote user from admin
async function demoteUser(userId) {
    try {
        await apiCall(`/acl/groups/admins/members/${userId}`, 'DELETE');
        await loadACLData();

        // Show feedback
        const user = aclUsers.find(u => u.id === userId);
        if (user) {
            showToast(`${user.username} demoted from Admin. Their messages no longer influence others in Protected Mode.`);
        }
    } catch (error) {
        console.error('Failed to demote user:', error);
        alert('Failed to demote user');
    }
}

// Show toast notification
function showToast(message) {
    // Create toast element
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: #667eea;
        color: white;
        padding: 15px 25px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        font-weight: 500;
        z-index: 1000;
        animation: slideIn 0.3s ease-out;
    `;
    toast.textContent = message;

    // Add animation
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {
            from { transform: translateX(400px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOut {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(400px); opacity: 0; }
        }
    `;
    document.head.appendChild(style);

    document.body.appendChild(toast);

    // Remove after 3 seconds
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}
