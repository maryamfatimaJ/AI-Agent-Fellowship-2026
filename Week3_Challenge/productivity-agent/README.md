# Trace

Trace is a personal productivity agent you talk to in plain English. It manages your tasks and notes, plans out your day, and can take real action for you — creating tasks, saving notes, setting reminders — but it always shows you an approval card first for anything that writes or can't easily be undone.

## What it does

- Chat with an AI agent to manage tasks and notes in plain English
- Create, list, update, and complete tasks with priority, status, due date, and tags
- Save and search your notes by keyword, category, or date range
- Paste in meeting notes and have it pull out action items as proposed tasks
- Ask it to build you a work plan for the day from your open tasks and free hours
- Set reminders and draft follow-up emails
- Riskier actions — creating several tasks at once, updating or completing a task, setting a reminder, or drafting an email — show you an approval card first, where you can approve, reject, or edit before anything actually happens. Quick, low-risk actions (adding one task, saving a note, listing or searching, generating a plan) go through right away.
- You can also manage tasks and notes directly from the Tasks and Notes boards, without going through chat at all
- Review a full Execution Logs history of every agent run — what you asked, which tools it used, whether it was approved, and how it turned out

## How it works

1. You type a request in the chat.
2. The agent decides whether it can just answer directly, or whether it needs to use a tool (like creating a task or searching your notes).
3. If the action would change or create data and is risky enough to need sign-off, it shows you exactly what it's about to do and waits for your approval.
4. Once approved (or if no approval was needed), it carries out the action, saves the result, and logs the whole run so you can review it later in Execution Logs.

## Tech used

- Flask, LangGraph, Google Gemini API, SQLite (via SQLAlchemy), Pydantic, HTML/CSS/JS

## How to run it

1. Install the requirements: `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in real values. At minimum you need a `GEMINI_API_KEY` (get one at https://aistudio.google.com/app/apikey) and a `SECRET_KEY` (any long random string) — the app won't start without these two. The other variables (`GENERATION_MODEL`, `DATABASE_URL`, `MAX_AGENT_STEPS`, `MAX_TOOL_RETRIES`, `TOOL_TIMEOUT_SECONDS`, `LOG_LEVEL`, `LOG_DIRECTORY`) already have sensible defaults.
3. Run it: `python app.py`
4. Open **http://127.0.0.1:5000** in your browser — don't open `templates/index.html` directly, it won't work without the Flask server running.

## Things to know

- Tasks and notes are saved in a real database file (`productivity_agent.db`), so they survive a restart. Chat memory (recent messages, the last list of tasks shown to you) is kept in memory only and resets whenever the server restarts.
- There's no login system — everyone using the app shares the same tasks and notes. Only the short-term chat memory is kept separate per browser session.
- The "draft follow-up email" tool only drafts and simulates sending — there's no real email account wired up, so nothing actually gets sent.
- It runs on Gemini's free tier by default, which has a daily quota. If you hit it, Trace will tell you to try again once the quota resets rather than failing silently.
