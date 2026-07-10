"""
services/rag.py
----------------
Handles everything related to storing document knowledge and answering
questions about it. This is the "brain" that connects ChromaDB (the
vector database) with the Gemini API (embeddings + text generation).

Public functions (these are what app.py and processor.py-driven flows call):

    add_document_to_index()      -> embeds chunks and stores them in ChromaDB
    delete_document_from_index() -> removes a document's chunks from ChromaDB
    refresh_all_embeddings()     -> re-processes every uploaded file from scratch
    get_answer_for_question()    -> retrieves relevant chunks and asks Gemini

Everything else below is a small private helper used by those four.
"""

import os
from datetime import datetime
import chromadb
from google import genai
from google.genai import errors as genai_errors
from google.genai.types import EmbedContentConfig

from services.processor import extract_text_from_file, split_text_into_chunks
from services.memory import get_conversation_history


# ============================================================
# CUSTOM EXCEPTION: GEMINI TEMPORARILY UNAVAILABLE
# ============================================================

class GeminiUnavailableError(Exception):
    """
    Raised when Gemini's API can't be reached right now — either it's
    overloaded (503) or the API key's quota is used up (429). app.py
    catches this and shows the user a clear message instead of a
    generic server-crash error.
    """
    pass


# ============================================================
# CONFIGURATION
# ============================================================

# NOTE: Gemini model names are updated by Google over time.
# Check https://ai.google.dev/gemini-api/docs/models for the current list
# if either of these stops working.
EMBEDDING_MODEL_NAME = "gemini-embedding-001"
GENERATION_MODEL_NAME = "gemini-2.5-flash"

CHROMA_DB_PATH = "/tmp/chroma_db"
COLLECTION_NAME = "documents"
UPLOAD_FOLDER = "uploads"

# How many chunks to retrieve from the vector database per question.
NUMBER_OF_CHUNKS_TO_RETRIEVE = 5

# Create the Gemini client once, using the key from our environment variables.
# (This uses the current google-genai SDK. The older google.generativeai
# package this used to run on was fully discontinued by Google.)
_genai_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


# ============================================================
# PRIVATE HELPER: GET (OR CREATE) THE CHROMADB COLLECTION
# ============================================================

# We keep the client and collection in module-level variables so we only
# connect to ChromaDB once, instead of reconnecting on every function call.
_chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
_collection = _chroma_client.get_or_create_collection(name=COLLECTION_NAME)


def get_collection():
    """Return the shared ChromaDB collection used to store document chunks."""
    return _collection


# ============================================================
# PRIVATE HELPER: CREATE AN EMBEDDING WITH GEMINI
# ============================================================

def generate_embedding(text, task_type):
    """
    Turn a piece of text into a list of numbers (an embedding) using
    Gemini's embedding model.

    task_type should be:
      - "RETRIEVAL_DOCUMENT" when embedding a chunk to STORE
      - "RETRIEVAL_QUERY"    when embedding a user's QUESTION
    Gemini uses this to slightly optimize the embedding for each purpose.
    """
    try:
        response = _genai_client.models.embed_content(
            model=EMBEDDING_MODEL_NAME,
            contents=text,
            config=EmbedContentConfig(task_type=task_type),
        )
    except genai_errors.ClientError as error:
        raise GeminiUnavailableError(
            "Gemini's API quota has been used up for now. "
            "Check your plan/billing at https://ai.google.dev/gemini-api/docs/rate-limits, "
            "or wait for the quota to reset."
        ) from error
    except genai_errors.ServerError as error:
        raise GeminiUnavailableError(
            "Gemini's servers are temporarily overloaded. Please try again in a moment."
        ) from error

    return response.embeddings[0].values


# ============================================================
# PUBLIC FUNCTION: ADD A DOCUMENT'S CHUNKS TO THE INDEX
# ============================================================

def add_document_to_index(document_id, filename, text_chunks):
    """
    Embed each chunk of a document and store it in ChromaDB, along with
    metadata so we can later show sources and delete the document.
    """
    collection = get_collection()

    chunk_ids = []
    chunk_embeddings = []
    chunk_metadatas = []

    for chunk_index, chunk_text in enumerate(text_chunks):
        if chunk_text.strip() == "":
            continue

        embedding = generate_embedding(chunk_text, task_type="RETRIEVAL_DOCUMENT")

        chunk_ids.append(document_id + "_chunk_" + str(chunk_index))
        chunk_embeddings.append(embedding)
        chunk_metadatas.append({
            "document_id": document_id,
            "filename": filename,
            "chunk_index": chunk_index,
            "text": chunk_text,
            "uploaded_at": datetime.now().isoformat(),
        })

    # ChromaDB requires "documents" (the raw text) separately from metadata,
    # so we pass the chunk text in both places for convenience.
    collection.add(
        ids=chunk_ids,
        embeddings=chunk_embeddings,
        metadatas=chunk_metadatas,
        documents=text_chunks,
    )


# ============================================================
# PRIVATE HELPER: FIND AN UPLOADED FILE ON DISK BY DOCUMENT ID
# ============================================================

def find_uploaded_file_path(document_id):
    """
    Our upload route saves files as "<document_id>_<original_name>".
    This scans the uploads folder and returns the full path of the file
    that starts with this document_id, or None if it isn't there.
    """
    for stored_filename in os.listdir(UPLOAD_FOLDER):
        if stored_filename.startswith(document_id + "_"):
            return os.path.join(UPLOAD_FOLDER, stored_filename)

    return None


# ============================================================
# PUBLIC FUNCTION: LIST EVERY INDEXED DOCUMENT
# ============================================================

def list_indexed_documents():
    """
    Group ChromaDB's chunk-level records by document, so the frontend can
    show one card per document instead of one card per chunk.

    Returns a list like:
        [ {"document_id": "...", "filename": "...", "chunk_count": 12}, ... ]
    """
    collection = get_collection()
    all_chunks = collection.get()

    documents_by_id = {}

    for metadata in all_chunks["metadatas"]:
        document_id = metadata["document_id"]

        if document_id not in documents_by_id:
            documents_by_id[document_id] = {
                "document_id": document_id,
                "filename": metadata["filename"],
                "chunk_count": 0,
                "uploaded_at": metadata.get("uploaded_at", ""),
            }

        documents_by_id[document_id]["chunk_count"] += 1

    documents = list(documents_by_id.values())
    documents.sort(key=lambda doc: doc["uploaded_at"], reverse=True)
    return documents


# ============================================================
# PUBLIC FUNCTION: GET OVERALL INDEX STATISTICS
# ============================================================

def get_index_stats():
    """Return simple counts used by the dashboard's statistics cards."""
    collection = get_collection()
    all_chunks = collection.get()

    unique_document_ids = set(
        metadata["document_id"] for metadata in all_chunks["metadatas"]
    )

    return {
        "total_documents": len(unique_document_ids),
        "total_chunks": len(all_chunks["ids"]),
    }


# ============================================================
# PUBLIC FUNCTION: REPROCESS ONE DOCUMENT
# ============================================================

def reprocess_single_document(document_id):
    """
    Re-read a single document from disk and rebuild just its chunks,
    without touching any other document. Used by the "Reprocess" option
    on a document card.

    Returns True if it found and reprocessed the file, False if the
    file couldn't be found on disk.
    """
    file_path = find_uploaded_file_path(document_id)

    if file_path is None:
        return False

    stored_filename = os.path.basename(file_path)
    _, _, original_name = stored_filename.partition("_")

    # Remove the old chunks first so we don't end up with duplicates.
    delete_document_from_index(document_id)

    document_text = extract_text_from_file(file_path)
    text_chunks = split_text_into_chunks(document_text)
    add_document_to_index(document_id, original_name, text_chunks)

    return True


# ============================================================
# PUBLIC FUNCTION: DELETE A DOCUMENT FROM THE INDEX
# ============================================================

def delete_document_from_index(document_id):
    """
    Remove every chunk belonging to a document from ChromaDB.
    Returns True if something was deleted, False if the document
    wasn't found.
    """
    collection = get_collection()

    # Check first so we can tell app.py whether the document actually existed.
    existing_chunks = collection.get(where={"document_id": document_id})

    if len(existing_chunks["ids"]) == 0:
        return False

    collection.delete(where={"document_id": document_id})
    return True


# ============================================================
# PUBLIC FUNCTION: REFRESH ALL EMBEDDINGS
# ============================================================

def refresh_all_embeddings():
    """
    Wipe the vector index and rebuild it from scratch by re-reading every
    file currently sitting in the uploads/ folder. Useful after changing
    chunking settings or switching embedding models.

    Returns the number of documents that were re-indexed.
    """
    collection = get_collection()

    # Clear out everything currently stored.
    all_existing = collection.get()
    if len(all_existing["ids"]) > 0:
        collection.delete(ids=all_existing["ids"])

    documents_refreshed = 0

    for stored_filename in os.listdir(UPLOAD_FOLDER):
        file_path = os.path.join(UPLOAD_FOLDER, stored_filename)

        # Our upload route saves files as "<document_id>_<original_name>".
        document_id, _, original_name = stored_filename.partition("_")

        document_text = extract_text_from_file(file_path)
        text_chunks = split_text_into_chunks(document_text)
        add_document_to_index(document_id, original_name, text_chunks)

        documents_refreshed += 1

    return documents_refreshed


# ============================================================
# PRIVATE HELPER: RETRIEVE RELEVANT CHUNKS FOR A QUESTION
# ============================================================

def retrieve_relevant_chunks(question):
    """
    Embed the user's question and find the most similar chunks
    stored in ChromaDB.
    """
    collection = get_collection()
    question_embedding = generate_embedding(question, task_type="RETRIEVAL_QUERY")

    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=NUMBER_OF_CHUNKS_TO_RETRIEVE,
    )

    return results


# ============================================================
# PRIVATE HELPER: FORMAT RECENT CONVERSATION HISTORY
# ============================================================

def format_conversation_history(history):
    """
    Turn the last few messages of a conversation into plain text the
    prompt can include, so Gemini can see what was already discussed
    and answer follow-up questions ("what about the second one?")
    correctly.

    Only the last 6 messages (3 back-and-forth exchanges) are included,
    to keep the prompt a reasonable size.
    """
    recent_messages = history[-6:]

    lines = []
    for entry in recent_messages:
        role_label = "User" if entry["role"] == "user" else "Assistant"
        lines.append(role_label + ": " + entry["message"])

    return "\n".join(lines)


# ============================================================
# PRIVATE HELPER: BUILD THE PROMPT SENT TO GEMINI
# ============================================================

def build_prompt(question, retrieved_metadatas, conversation_history):
    """
    Combine the retrieved chunks, recent conversation history, and the
    user's question into a single prompt that instructs Gemini to answer
    ONLY using the provided context.
    """
    context_sections = []

    for metadata in retrieved_metadatas:
        section = "Source: " + metadata["filename"] + "\n" + metadata["text"]
        context_sections.append(section)

    context_text = "\n\n---\n\n".join(context_sections)

    history_text = format_conversation_history(conversation_history)
    history_block = ""
    if history_text != "":
        history_block = "Recent conversation:\n" + history_text + "\n\n"

    prompt = (
        "You are an assistant that answers questions using ONLY the context below. "
        "If the answer isn't in the context, say you don't have enough information. "
        "Use the recent conversation to understand follow-up questions "
        "(for example, \"the second one\" or \"what about that\").\n\n"
        + history_block +
        "Context:\n" + context_text + "\n\n"
        "Question: " + question + "\n\n"
        "Answer:"
    )

    return prompt


# ============================================================
# PRIVATE HELPER: CALL GEMINI TO GENERATE THE FINAL ANSWER
# ============================================================

def generate_answer_with_gemini(prompt):
    """Send the prompt to Gemini's generative model and return the text reply."""
    try:
        response = _genai_client.models.generate_content(
            model=GENERATION_MODEL_NAME,
            contents=prompt,
        )
    except genai_errors.ClientError as error:
        raise GeminiUnavailableError(
            "Gemini's API quota has been used up for now. "
            "Check your plan/billing at https://ai.google.dev/gemini-api/docs/rate-limits, "
            "or wait for the quota to reset."
        ) from error
    except genai_errors.ServerError as error:
        raise GeminiUnavailableError(
            "Gemini's servers are temporarily overloaded. Please try again in a moment."
        ) from error

    return response.text


# ============================================================
# PUBLIC FUNCTION: GET AN ANSWER FOR A USER'S QUESTION
# ============================================================

def get_answer_for_question(question, session_id):
    """
    The main RAG pipeline:
    1. Retrieve the most relevant chunks for this question.
    2. Build a prompt that grounds Gemini in those chunks.
    3. Generate the answer.
    4. Return the answer along with the sources used, so the frontend
       can display citations.

    session_id is used to pull recent conversation history, so follow-up
    questions ("what about the second one?") can be understood correctly.
    """
    results = retrieve_relevant_chunks(question)

    # ChromaDB returns results as lists-of-lists (one list per query embedding).
    # Since we only send one question at a time, we only need index [0].
    retrieved_metadatas = results["metadatas"][0]
    retrieved_distances = results["distances"][0]

    if len(retrieved_metadatas) == 0:
        return {
            "answer": "I don't have any documents indexed yet to answer that.",
            "sources": [],
        }

    conversation_history = get_conversation_history(session_id)
    prompt = build_prompt(question, retrieved_metadatas, conversation_history)
    answer_text = generate_answer_with_gemini(prompt)

    sources = build_sources_list(retrieved_metadatas, retrieved_distances)

    return {
        "answer": answer_text,
        "sources": sources,
    }


# ============================================================
# PRIVATE HELPER: FORMAT SOURCES FOR THE FRONTEND
# ============================================================

def build_sources_list(metadatas, distances):
    """
    Turn ChromaDB's raw metadata and distances into the simple source
    format the frontend's source cards expect.
    """
    sources = []

    for metadata, distance in zip(metadatas, distances):
        # ChromaDB's "distance" is smaller-is-better. We convert it into a
        # friendlier 0-100 "relevance score" for the UI's relevance ring.
        relevance_score = round((1 - distance) * 100)

        sources.append({
            "filename": metadata["filename"],
            "chunk_index": metadata["chunk_index"],
            "snippet": metadata["text"],
            "relevance_score": relevance_score,
        })

    return sources
