const chatBox = document.getElementById('chat-box');
const input = document.getElementById('message');
const form = document.getElementById('chat-form');
const typingIndicator = document.getElementById('typing-indicator');
const tourSuggestions = document.getElementById('tour-suggestions');
const sendBtn = document.getElementById('send-btn');

let conversationId = sessionStorage.getItem('sam-conversation-id') || '';
let isSending = false;

const scrollToBottom = () => {
    chatBox.scrollTo({ top: chatBox.scrollHeight, behavior: 'smooth' });
};

const addMessage = (text, sender = 'bot') => {
    if (!text) return;
    const bubble = document.createElement('div');
    bubble.className = `message ${sender}`;
    bubble.innerText = text;
    chatBox.appendChild(bubble);
    scrollToBottom();
};

const toggleTyping = (show) => {
    typingIndicator.classList.toggle('hidden', !show);
};

const setSuggestions = (items = []) => {
    tourSuggestions.innerHTML = '';
    if (!items.length) {
        const empty = document.createElement('p');
        empty.className = 'chat-subtitle';
        empty.textContent = 'SAM te informará apenas se abran nuevos cupos.';
        tourSuggestions.appendChild(empty);
        return;
    }

    items.forEach((item) => {
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'tour-chip';
        chip.textContent = item;
        chip.addEventListener('click', () => {
            input.value = item.split('·')[0].replace(/^[0-9]+\.\s*/, '').trim();
            input.focus();
        });
        tourSuggestions.appendChild(chip);
    });
};

const initializeChat = async () => {
    try {
        const res = await fetch('/chat/init');
        if (!res.ok) throw new Error('No se pudo iniciar el chat');
        const data = await res.json();
        conversationId = data.conversation_id;
        sessionStorage.setItem('sam-conversation-id', conversationId);
        addMessage(data.reply, 'bot');
        setSuggestions(data.suggested_tours);
    } catch (error) {
        addMessage('No pude conectarme con SAM en este momento. Intenta nuevamente. 🙏', 'bot');
    }
};

const sendMessage = async () => {
    const text = input.value.trim();
    if (!text || isSending) return;

    addMessage(text, 'user');
    input.value = '';
    toggleTyping(true);
    isSending = true;
    sendBtn.disabled = true;

    try {
        const res = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: text,
                conversation_id: conversationId,
            }),
        });

        if (!res.ok) {
            throw new Error('Error al contactar el servidor');
        }

        const data = await res.json();
        conversationId = data.conversation_id;
        sessionStorage.setItem('sam-conversation-id', conversationId);
        addMessage(data.reply, 'bot');
        setSuggestions(data.suggested_tours);
    } catch (error) {
        addMessage('Hubo un problema de conexión. Por favor intenta nuevamente.', 'bot');
    } finally {
        toggleTyping(false);
        isSending = false;
        sendBtn.disabled = false;
        input.focus();
    }
};

form.addEventListener('submit', (event) => {
    event.preventDefault();
    sendMessage();
});

input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
});

window.addEventListener('load', () => {
    if (!conversationId) {
        const randomId = typeof crypto !== 'undefined' && crypto.randomUUID
            ? crypto.randomUUID()
            : `${Date.now()}-${Math.random()}`;
        conversationId = randomId;
        sessionStorage.setItem('sam-conversation-id', conversationId);
    }
    initializeChat();
    input.focus();
});
