from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates

from .schemas import ChatRequest, ChatResponse
from .openai_client import chat_with_openai

app = FastAPI(
    title="Montebello Tour Chatbot (Prototype)",
    description="Chatbot prototype for school tour registration.",
    version="0.1.0"
)

# CORS (allow all for prototype)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# STATIC & TEMPLATES
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    reply = chat_with_openai(req.message)
    return ChatResponse(reply=reply)
