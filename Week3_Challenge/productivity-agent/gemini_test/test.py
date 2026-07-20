"""
gemini_test/test.py
----------------------
Minimal, standalone Gemini API connectivity test — deliberately has NO
dependency on the rest of the Trace app (no Flask, no config.py, no
database). The only goal here is to isolate whether a problem talking
to Gemini is caused by the API key/account/project, or by something in
the main app's code.

Run with: py test.py   (from inside this gemini_test/ folder)
"""

import os
import sys
from pathlib import Path

# ============================================================
# STEP 1: LOAD THE API KEY
# ------------------------------------------------------------
# Look for a .env file in the PROJECT ROOT (one level up from this
# folder), not inside gemini_test/ itself — that's where the main
# app's real .env already lives, and this script deliberately reuses
# it instead of needing its own copy of the key.
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

if ENV_PATH.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(ENV_PATH)
        print(f"Loaded environment variables from: {ENV_PATH}")
    except ImportError:
        print("python-dotenv isn't installed — install it with:")
        print("    py -m pip install -r requirements.txt")
        sys.exit(1)
else:
    print(f"No .env file found at {ENV_PATH} — relying on already-set environment variables, if any.")

api_key = os.environ.get("GEMINI_API_KEY", "")
model_name = os.environ.get("GENERATION_MODEL", "gemini-2.5-flash-lite")

# ============================================================
# STEP 2: REPORT WHETHER A KEY WAS FOUND (never print the whole thing)
# ============================================================

if not api_key:
    print()
    print("GEMINI_API_KEY: NOT FOUND. Nothing to test against — set it in the .env")
    print("file at the project root, or export it as an environment variable, then re-run.")
    sys.exit(1)

if len(api_key) >= 8:
    masked = f"{api_key[:4]}...{api_key[-4:]}"
else:
    masked = "(too short to mask safely — check this looks like a real key)"

print()
print(f"GEMINI_API_KEY found: {masked}  (length: {len(api_key)})")
print(f"GENERATION_MODEL: {model_name}")
print()

# ============================================================
# STEP 3: MAKE THE SIMPLEST POSSIBLE CALL
# ============================================================

try:
    from google import genai
except ImportError:
    print("google-genai isn't installed — install it with:")
    print("    py -m pip install -r requirements.txt")
    sys.exit(1)

print("Sending a test prompt to Gemini...")
print("-" * 60)

try:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model_name,
        contents="Say hello in one word.",
    )

    print("SUCCESS")
    print("-" * 60)
    print("Model response:", response.text)

except Exception as error:
    # Deliberately NOT simplified — every detail available is printed,
    # since the whole point of this script is to see the real error.
    print("FAILURE")
    print("-" * 60)
    print("Exception type:", type(error).__name__)

    status_code = getattr(error, "code", None)
    if status_code is not None:
        print("Status code:", status_code)

    status_text = getattr(error, "status", None)
    if status_text is not None:
        print("Status:", status_text)

    details = getattr(error, "details", None)
    if details is not None:
        print("Full error details:", details)

    print()
    print("Full exception message:")
    print(str(error))
    sys.exit(1)
