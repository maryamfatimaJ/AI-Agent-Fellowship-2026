from flask import Flask, render_template, request, redirect, url_for, session
from google import genai
from flask import Response
from google.genai import types
from dotenv import load_dotenv
import markdown
import os

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv(
    "SECRET_KEY",
    "temporary-development-secret"
)

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError(
        "GEMINI_API_KEY is missing. Add it to the .env file."
    )

client = genai.Client(api_key=api_key)


@app.route("/")
def home():
    messages = session.get("messages", [])
    error = session.pop("error", None)

    return render_template(
        "index.html",
        messages=messages,
        error=error
    )


@app.route("/chat", methods=["POST"])
def chat():
    prompt = request.form.get("prompt", "").strip()

    system_prompt = request.form.get(
        "system_prompt",
        "You are a helpful AI assistant."
    ).strip()

    selected_model = request.form.get(
        "model",
        "gemini-3.5-flash"
    )

    if not prompt:
        session["error"] = "Please enter a message."
        return redirect(url_for("home"))

    messages = session.get("messages", [])

    messages.append({
        "role": "user",
        "content": prompt
    })

    try:
        response = client.models.generate_content(
            model=selected_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt
            )
        )

        raw_reply = response.text or "No response was generated."

        ai_reply = markdown.markdown(
            raw_reply,
            extensions=["fenced_code", "tables"]
        )

    except Exception as error:
        ai_reply = (
            "Sorry, the AI request failed. "
            "Please check your API key, internet connection, or selected model."
        )

        print("Gemini API Error:", error)

    messages.append({
        "role": "assistant",
        "content": ai_reply
    })

    session["messages"] = messages

    return redirect(url_for("home"))

@app.route("/export")
def export_chat():
    messages = session.get("messages", [])

    if not messages:
        session["error"] = "There is no conversation to export."
        return redirect(url_for("home"))

    lines = []

    for message in messages:
        role = "You" if message["role"] == "user" else "AI"
        lines.append(f"{role}:\n{message['content']}\n")

    chat_text = "\n".join(lines)

    return Response(
        chat_text,
        mimetype="text/plain",
        headers={
            "Content-Disposition":
            "attachment; filename=ai_workspace_chat.txt"
        }
    )

@app.route("/clear")
def clear_chat():
    session.pop("messages", None)
    session.pop("error", None)

    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)