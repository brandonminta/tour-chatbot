# Montebello TourBot

This document provides a presentation-style overview of the Montebello TourBot web application, covering the stack, runtime architecture, data model, and key workflows.

## Technologies at a Glance
- **FastAPI** – asynchronous Python web framework that powers the HTTP API and serves static assets.
- **SQLite** – embedded relational database used for tour dates, course capacity, and registrations without extra services.
- **OpenAI Responses API** – LLM-powered chat and data-extraction pipeline for guiding families through tour registration.
- **HTML/CSS/Vanilla JS** – lightweight front-end delivered by FastAPI; no bundler required.
- **python-dotenv** – loads the `OPENAI_API_KEY` environment variable for the OpenAI client.

## Architecture
- **Client UI**: `/` renders `templates/index.html`, which loads `static/chat.js` and `static/style.css` to present the chat experience and handle user input.
- **FastAPI Layer**: `main.py` defines routes for chat initialization (`/chat/init`), chat turns (`/chat`), static files, and the thank-you page. It also configures CORS and mounts the static directory.
- **Conversation Memory**: `ConversationThread` stores the recent message history and a compressed summary. The summary is updated via `state_manager.extract_state` to save tokens when calling the LLM.
- **LLM Orchestration**: `tourbot_agent.py` builds the message payload for the OpenAI Responses API, providing system prompts plus optional tour and capacity context. It registers the `register_user` tool definition from `functions.py` so the model can trigger registrations.
- **Function Execution**: When the model returns a tool call, `functions.execute_register_user` validates arguments, reserves course capacity, and persists the registration in SQLite.
- **Data Access Layer**: `database.py` offers hand-written SQL helpers for creating/reading tours, courses, and registrations, seeding sample data, and reserving capacity or waitlist slots.

## Request Flow
1. **Page Load**: The browser fetches `/` → `index.html`, which immediately calls `/chat/init` via `initializeChat()` in `static/chat.js`. A new `conversation_id` is stored in `sessionStorage` and the first assistant message is rendered.
2. **User Message**: Submitting the form sends `/chat` with the message and `conversation_id`. The server appends the user turn to in-memory history and builds JSON context from `list_active_tours` and `list_courses`.
3. **LLM Turn**: `run_tourbot()` sends history, summary, and context to OpenAI with the `register_user` tool exposed. The model can either respond with text or request a function call.
4. **Function Call Path**: If the model calls `register_user`, the server parses the JSON arguments, validates the `tour_date_id`, reserves course capacity, and creates a registration via `create_registration`. A success response marks the chat stage as `completed` and the front-end redirects to `/gracias`.
5. **Normal Reply Path**: If the model replies with text, the assistant message is stored and returned to the client to render.
6. **Thank You Page**: Completing registration shows `templates/thank_you.html`, a static confirmation screen.

## Key Backend Components
- **`main.py`** – FastAPI entry point; orchestrates conversation state, builds context JSON, handles tool calls, and returns `ChatResponse`/`InitChatResponse` models. CORS and static mounts are configured here.
- **`tourbot_agent.py`** – Defines the system prompt and constructs OpenAI `input` messages. Invokes `_client.responses.create` with the `REGISTER_USER_FUNCTION` tool schema and temperature/length settings.
- **`functions.py`** – Contains the JSON schema for the `register_user` tool and the execution logic that normalizes names/emails, verifies tour IDs, reserves course capacity, and creates the DB row.
- **`state_manager.py`** – Uses the OpenAI API (when available) to extract a compact JSON snapshot of user data (name/email/phone/grades/intent/readiness) from the last few turns; used to keep `ConversationThread.summary` concise.
- **`openai_client.py`** – Loads the API key, instantiates the reusable OpenAI client, and offers a `polish_reply` helper for tone smoothing (not currently called from `main.py`).
- **`schemas.py`** – Pydantic request/response models ensuring the chat endpoints return predictable shapes.
- **`database.py`** – Pure-SQLite helper module: initializes tables, seeds tour dates/courses, lists active tours and course capacities, matches grade names, reserves capacity or waitlist counts, and persists registrations.

## Database Schema
`init_db()` creates three tables on startup if they do not exist:
- **`tour_dates`**: `id` (PK), `date` (ISO text), `capacity`, `registered`, `status` (`open`/`closed`). Seeded with upcoming tour dates spaced every 3 days.
- **`courses`**: `id` (PK), `name`, `capacity_available`, `waitlist_count`. Seeded with grade-level capacities (e.g., "Inicial", "1° EGB").
- **`registrations`**: `id` (PK), `first_name`, `last_name`, `email`, `phone`, `grade_interest`, `tour_date_id` (FK → `tour_dates`), `wait_listed` (boolean).

### Capacity Logic
- `reserve_course_interest` decrements `capacity_available` for matched courses or increments `waitlist_count` if full, returning whether any grade was wait-listed.
- `create_registration` always stores the registration and returns a `wait_listed` flag that can be forced when course capacity is exceeded.

## Front-End Experience
- **Layout**: `templates/index.html` renders a hero header and chat card; `style.css` defines the modern, responsive look; `thank_you.html` provides a confirmation state.
- **Behavior**: `static/chat.js` manages the chat box, optimistic user message rendering, typing indicator, connection banner, retry logic, and redirect on successful registration. Enter submits the form, and sessions persist through `sessionStorage`.

## Running the App Locally
1. Install dependencies: `pip install -r requirements.txt`.
2. Set `OPENAI_API_KEY` in your environment (or `.env`) if you want live LLM responses.
3. Start the server: `uvicorn app.main:app --reload --port 8000`.
4. Open `http://localhost:8000` in your browser to start chatting with SAM.

