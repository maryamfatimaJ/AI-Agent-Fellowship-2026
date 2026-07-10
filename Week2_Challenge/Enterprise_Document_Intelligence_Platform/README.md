# Enterprise Document Intelligence Platform

Upload your documents, then ask questions about them in plain English. The app finds the relevant parts of your documents and uses AI to answer, showing you exactly where the answer came from.

## What it does

- Upload PDF, DOCX, TXT, or Markdown files
- Ask questions about your documents in a chat window
- Get answers with the source document and text snippet shown
- Start new chats or come back to old ones
- View, delete, or reprocess any uploaded document
- Export your chat as a text file or PDF
- See simple stats: how many documents, chunks, and conversations you have

## How it works

1. When you upload a file, the app reads the text and splits it into small chunks.
2. Each chunk is turned into an embedding (a list of numbers representing its meaning) and stored in a database called ChromaDB.
3. When you ask a question, the app finds the chunks that best match your question.
4. Those chunks are sent to Google's Gemini AI along with your question, and Gemini writes the answer.

## Tech used

- **Flask** – the Python web server
- **ChromaDB** – stores the document chunks for searching
- **Gemini API** – generates embeddings and writes answers
- **HTML / CSS / JavaScript** – the interface (no frameworks)

## How to run it

**1. Install the requirements**
```bash
pip install -r requirements.txt
```

**2. Add your API key**

Create a file called `.env` in the project folder and add:
```
GEMINI_API_KEY=your-gemini-api-key
SECRET_KEY=any-random-text
```
Get a free key at [Google AI Studio](https://aistudio.google.com/app/apikey).

**3. Run the app**
```bash
python app.py
```

**4. Open it in your browser**

Go to **http://127.0.0.1:5000**

⚠️ Don't open `index.html` directly by double-clicking it — it has to be opened through this link, or the styling won't load.

## Things to know

- Chat history is stored in memory, so it resets if you restart the app.
- There's no login system — anyone using the same browser session sees the same chats.
- The free Gemini API key has usage limits, so heavy use may show a "please try again" message sometimes. That's normal.