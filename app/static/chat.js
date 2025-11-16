const chatBox = document.getElementById("chat-box");
const input = document.getElementById("message");

function addMessage(text, sender) {
    const div = document.createElement("div");
    div.classList.add("msg", sender);
    div.innerText = text;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
}

async function sendMessage() {
    const text = input.value.trim();
    if (!text) return;

    addMessage(text, "user");
    input.value = "";

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ message: text }),
        });

        if (!response.ok) {
            addMessage("Error contacting server.", "bot");
            return;
        }

        const data = await response.json();
        addMessage(data.reply, "bot");
    } catch (err) {
        addMessage("Connection error.", "bot");
    }
}

// Initial greeting
window.onload = () => {
    addMessage("Hola, soy el asistente de admisiones de Montebello. ¿Cómo puedo ayudarte hoy?", "bot");
};
