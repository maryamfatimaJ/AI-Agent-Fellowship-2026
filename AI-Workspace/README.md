# ✦ AI Workspace

AI Workspace is a full-stack AI chat application that provides a unified interface for interacting with AI models.

The application uses the Google Gemini API and allows users to customize AI responses through system prompts, model selection, and ready-made prompt templates.

## Live Demo

[Open AI Workspace](https://ai-agent-fellowship-2026-qoh2-wzylwsmaj.vercel.app/)

## Features

- Natural AI chat interface
- Custom system prompt
- AI model selection
- Prompt templates
- Session-based conversation history
- Markdown-formatted AI responses
- Empty prompt validation
- Invalid API key handling
- Connection failure handling
- Responsive user interface
- Light and dark theme
- Export chat as a text file
- Clear current conversation

## Prompt Templates

- Summarize Text
- Explain Code
- Generate Ideas
- Rewrite Content
- Translate
- Create Email
- Brainstorm

## Tech Stack

- **Frontend:** HTML, CSS, JavaScript
- **Backend:** Python Flask
- **AI API:** Google Gemini API
- **Markdown Rendering:** Python Markdown
- **Deployment:** Vercel

## Project Structure

```text
AI-Workspace/
│
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
│
├── templates/
│   └── index.html
│
└── static/
    ├── style.css
    └── favicon.png
```

## Installation

### Clone the repository:

git clone YOUR_GITHUB_REPOSITORY_URL

### Open the project folder:

cd AI-Agent-Fellowship-2026/AI-Workspace

### Install the required packages:

py -m pip install -r requirements.txt
Environment Variables

### Create a .env file inside the AI-Workspace folder:

GEMINI_API_KEY=your_gemini_api_key
SECRET_KEY=your_random_secret_key

Do not upload the real .env file to GitHub.

Your .gitignore should contain:

.env
__pycache__/
*.pyc
Run Locally

### Run the Flask application:

py app.py

Open the following URL in your browser:

http://127.0.0.1:5000
