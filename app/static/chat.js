const chatBox = document.getElementById('chat-box');
const input = document.getElementById('message');
const form = document.getElementById('chat-form');
const typingIndicator = document.getElementById('typing-indicator');
const connectionBanner = document.getElementById('connection-banner');
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

const setConnectionBanner = (text = '', state = 'warning') => {
    connectionBanner.textContent = text;
    connectionBanner.className = `connection-banner ${state}`;
    connectionBanner.classList.toggle('hidden', !text);
};

const requestWithRetry = async (url, options = {}, attempts = 2) => {
    let lastError;
    for (let i = 0; i < attempts; i += 1) {
        try {
            const res = await fetch(url, options);
            if (!res.ok) throw new Error(`Error ${res.status}`);
            return res;
        } catch (error) {
            lastError = error;
            await new Promise((resolve) => setTimeout(resolve, 400 * (i + 1)));
        }
    }
    throw lastError;
};

const initializeChat = async ({ silent = false } = {}) => {
    try {
        setConnectionBanner('Conectando con SAM…', 'ok');
        const res = await requestWithRetry('/chat/init');
        if (!res.ok) throw new Error('No se pudo iniciar el chat');
        const data = await res.json();
        conversationId = data.conversation_id;
        sessionStorage.setItem('sam-conversation-id', conversationId);
        if (!silent) {
            addMessage(data.reply, 'bot');
        }
        setConnectionBanner('', 'ok');
    } catch (error) {
        addMessage('No pude conectarme con SAM en este momento. Intenta nuevamente.', 'bot');
        setConnectionBanner('Sin conexión. Reintentaremos en unos segundos…', 'error');
        setTimeout(() => initializeChat({ silent: true }), 1200);
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
        const res = await requestWithRetry(
            '/chat',
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    conversation_id: conversationId,
                }),
            },
            2,
        );

        if (!res.ok) throw new Error('Error al contactar el servidor');

        const data = await res.json();
        conversationId = data.conversation_id;
        sessionStorage.setItem('sam-conversation-id', conversationId);

        addMessage(data.reply, 'bot');

        if (data.registration_completed) {
            setTimeout(() => {
                window.location.href = '/gracias';
            }, 700);
        }

    } catch (error) {
        addMessage('Hubo un problema de conexión. Restableciendo la sesión…', 'bot');
        setConnectionBanner('Se perdió la conexión. Intentando reconectar…', 'warning');
        await initializeChat({ silent: true });
        addMessage('Listo, volvimos a conectarnos. ¿Continuamos con tu registro?', 'bot');
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
        const randomId = crypto.randomUUID
            ? crypto.randomUUID()
            : `${Date.now()}-${Math.random()}`;
        conversationId = randomId;
        sessionStorage.setItem('sam-conversation-id', conversationId);
    }
    initializeChat();
    input.focus();
});
