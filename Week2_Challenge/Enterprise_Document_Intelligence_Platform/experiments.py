"""
experiments.py
--------------
Run this from your project root (same folder as app.py) to perform
all four experiments for Assignment 4.

It uses:
  - Your EXISTING split_text_into_chunks() from services/processor.py
    (no new chunking code needed — just different arguments)
  - Your EXISTING Gemini setup for prompt/generation experiments
  - A SECOND, free, local embedding model (sentence-transformers)
    for Experiment 4, since the app currently only has Gemini's

Before running:
    pip install sentence-transformers

Usage:
    python experiments.py

Copy the printed output into your Assignment 4 report.
"""

import os
import time
from dotenv import load_dotenv

load_dotenv()

from services.processor import extract_text_from_file, split_text_into_chunks


# ============================================================
# SETUP: pick one real document from uploads/ to test with
# ============================================================

UPLOAD_FOLDER = "uploads"


def pick_a_test_document():
    files = [f for f in os.listdir(UPLOAD_FOLDER) if not f.startswith(".")]
    if not files:
        raise SystemExit("No files found in uploads/. Upload at least one document first, then rerun.")
    chosen = files[0]
    print("Using test document:", chosen)
    return os.path.join(UPLOAD_FOLDER, chosen)


test_file_path = pick_a_test_document()
document_text = extract_text_from_file(test_file_path)
print("Document length:", len(document_text), "characters\n")


# ============================================================
# EXPERIMENT 1: CHUNK SIZE
# ============================================================

def run_experiment_1():
    print("=" * 60)
    print("EXPERIMENT 1: CHUNK SIZE (overlap fixed at 100)")
    print("=" * 60)

    for size in [300, 500, 1000]:
        chunks = split_text_into_chunks(document_text, chunk_size=size, overlap=100)
        lengths = [len(c) for c in chunks]
        avg_len = sum(lengths) / len(lengths) if chunks else 0

        print(f"\nchunk_size = {size}")
        print(f"  Number of chunks produced: {len(chunks)}")
        print(f"  Average chunk length: {avg_len:.0f} characters")
        if chunks:
            print(f"  First chunk preview: {chunks[0][:120]!r}...")
    print()


run_experiment_1()


# ============================================================
# EXPERIMENT 2: CHUNK OVERLAP
# ============================================================

def run_experiment_2():
    print("=" * 60)
    print("EXPERIMENT 2: CHUNK OVERLAP (chunk_size fixed at 500)")
    print("=" * 60)

    for overlap in [0, 100, 200]:
        chunks = split_text_into_chunks(document_text, chunk_size=500, overlap=overlap)
        print(f"\noverlap = {overlap}")
        print(f"  Number of chunks produced: {len(chunks)}")

        if len(chunks) >= 2:
            end_of_first = chunks[0][-60:]
            start_of_second = chunks[1][:60]
            print(f"  End of chunk 1:   ...{end_of_first!r}")
            print(f"  Start of chunk 2: {start_of_second!r}...")
            print("  (With overlap=0, a sentence here may look cut in half.")
            print("   With overlap=100 or 200, the two should share some text.)")
    print()


run_experiment_2()


# ============================================================
# EXPERIMENT 3: PROMPT TEMPLATES
# ============================================================

from google import genai

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
GENERATION_MODEL = "gemini-2.5-flash"

# Use the same fixed context for every prompt, so the comparison is fair —
# only the prompt wording changes, not the information available.
sample_chunks = split_text_into_chunks(document_text, chunk_size=500, overlap=100)[:3]
context_text = "\n\n---\n\n".join(sample_chunks)
test_question = "What is this document about?"

PROMPT_TEMPLATES = {
    "strict_grounding": (
        "You are an assistant that answers ONLY using the context below. "
        "If the answer isn't in the context, say you don't have enough information.\n\n"
        f"Context:\n{context_text}\n\nQuestion: {test_question}\n\nAnswer:"
    ),
    "loose_no_instruction": (
        f"Context:\n{context_text}\n\nQuestion: {test_question}\n\nAnswer:"
    ),
    "citation_required": (
        "Answer the question using the context below. In your answer, mention which "
        "part of the context you used to support your answer.\n\n"
        f"Context:\n{context_text}\n\nQuestion: {test_question}\n\nAnswer:"
    ),
}


def run_experiment_3():
    print("=" * 60)
    print("EXPERIMENT 3: PROMPT TEMPLATES")
    print("=" * 60)

    for name, prompt in PROMPT_TEMPLATES.items():
        print(f"\n--- {name} ---")
        try:
            response = client.models.generate_content(model=GENERATION_MODEL, contents=prompt)
            print(response.text)
        except Exception as error:
            print("Request failed:", error)
        time.sleep(1)  # small pause to be gentle on API rate limits
    print()


run_experiment_3()


# ============================================================
# EXPERIMENT 4: EMBEDDING MODELS
# ============================================================

def run_experiment_4():
    print("=" * 60)
    print("EXPERIMENT 4: EMBEDDING MODELS (Gemini vs. a local model)")
    print("=" * 60)

    from google.genai.types import EmbedContentConfig
    sample_text = sample_chunks[0]

    # Model 1: Gemini's embedding (the one already used in the app)
    try:
        gemini_result = client.models.embed_content(
            model="gemini-embedding-001",
            contents=sample_text,
            config=EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
        )
        gemini_vector = gemini_result.embeddings[0].values
        print(f"\nGemini (gemini-embedding-001): vector length = {len(gemini_vector)}")
    except Exception as error:
        print("Gemini embedding failed:", error)
        gemini_vector = None

    # Model 2: a free, local model — this is the "second model" the
    # assignment asks for, since the app doesn't have one built in yet
    try:
        from sentence_transformers import SentenceTransformer
        local_model = SentenceTransformer("all-MiniLM-L6-v2")
        local_vector = local_model.encode(sample_text)
        print(f"Local (all-MiniLM-L6-v2): vector length = {len(local_vector)}")
    except ImportError:
        print("\nsentence-transformers isn't installed yet. Run this first, then rerun this script:")
        print("  pip install sentence-transformers")
        local_vector = None
    except Exception as error:
        print("Local embedding failed:", error)
        local_vector = None

    if gemini_vector is not None and local_vector is not None:
        print("\nBoth models produced an embedding successfully.")
        print("Their vector lengths differ because they're different models with")
        print("different internal designs — that's expected, not an error. Each")
        print("model's vectors are only meant to be compared against its OWN")
        print("other vectors, never mixed between the two models.")
    print()


run_experiment_4()

print("=" * 60)
print("All experiments finished. Copy the output above into your report.")
print("=" * 60)