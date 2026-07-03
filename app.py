from flask import Flask, render_template, request, redirect, url_for, session
from google import genai
from google.genai import types
import os

app = Flask(__name__)

# Flask session use karne ke liye secret key
app.secret_key = "ai-workspace-secret-key"

# PowerShell ke GEMINI_API_KEY environment variable ko read karega
client = genai.Client()


@app.route("/")
def home():
    # Agar abhi tak history nahi bani, empty list use hogi
    messages = session.get("messages", [])

    return render_template(
        "index.html",
        messages=messages
    )


@app.route("/chat", methods=["POST"])
def chat():
    # HTML form se values receive karna
    prompt = request.form.get("prompt", "").strip()

    system_prompt = request.form.get(
        "system_prompt",
        "You are a helpful AI assistant."
    ).strip()

    selected_model = request.form.get(
        "model",
        "gemini-3.5-flash"
    )

    # Empty prompt handling
    if not prompt:
        session["error"] = "Please enter a message."
        return redirect(url_for("home"))

    # Purani conversation lena
    messages = session.get("messages", [])

    # User message history mein add karna
    messages.append({
        "role": "user",
        "content": prompt
    })

    try:
        # Actual Gemini API call
        response = client.models.generate_content(
            model=selected_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt
            )
        )

        ai_reply = response.text or "No response was generated."

    except Exception as error:
        ai_reply = (
            "Sorry, the AI request failed. "
            "Please check your API key, internet connection, or selected model."
        )

        print("Gemini API Error:", error)

    # AI response history mein add karna
    messages.append({
        "role": "assistant",
        "content": ai_reply
    })

    # Updated history session mein save karna
    session["messages"] = messages

    return redirect(url_for("home"))


@app.route("/clear")
def clear_chat():
    session.pop("messages", None)
    session.pop("error", None)

    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)