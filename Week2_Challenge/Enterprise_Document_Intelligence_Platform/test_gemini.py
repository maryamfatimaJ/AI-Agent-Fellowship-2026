"""
test_gemini.py
--------------
Run this by itself to check whether your Gemini API key and model
actually work, completely separate from Flask.

Usage:
    python test_gemini.py
"""

import os
from dotenv import load_dotenv
from google import genai
from google.genai.types import EmbedContentConfig

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
print("Loaded API key starts with:", (api_key[:8] + "...") if api_key else "NOTHING FOUND")

client = genai.Client(api_key=api_key)

print("\n--- Testing embedding ---")
try:
    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents="hello world",
        config=EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
    )
    print("Embedding OK. Vector length:", len(result.embeddings[0].values))
except Exception as error:
    print("EMBEDDING FAILED:", error)

print("\n--- Testing generation ---")
try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Say hello in one short sentence.",
    )
    print("Generation OK. Reply:", response.text)
except Exception as error:
    print("GENERATION FAILED:", error)