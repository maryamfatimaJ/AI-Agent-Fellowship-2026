"""
tools/note_tools.py
---------------------
Note-related tools the agent can call.
"""

from database import repository
from tools.logging_setup import get_tool_logger
from schemas import (
    NoteCreate, NoteOut,
    SearchNotesInput, SearchNotesOutput, NoteSearchResult,
)

logger = get_tool_logger("note_tools")


# ============================================================
# TOOL 5: SEARCH NOTES
# ============================================================

SEARCH_NOTES_REQUIRES_APPROVAL = False  # read-only


def search_notes(data: SearchNotesInput) -> SearchNotesOutput:
    """
    Search notes by keyword. Returns each match with a simple relevance
    score based on where the query text was found.

    This is keyword search, not semantic search — matching by meaning
    rather than exact words is recommended by the assignment but
    explicitly marked optional for Week 3. The output shape here
    (NoteSearchResult with a match_score) is deliberately the same
    shape a future semantic-search version would return, so upgrading
    later wouldn't require changing anything that calls this tool.
    """
    logger.info(
        "search_notes called: query=%r category=%s date_from=%s date_to=%s",
        data.query, data.category, data.date_from, data.date_to,
    )
    matches = repository.search_notes(data.query, category=data.category, date_from=data.date_from, date_to=data.date_to)

    results = [
        NoteSearchResult(note=note, match_score=_keyword_match_score(note, data.query))
        for note in matches
    ]

    # Best matches first.
    results.sort(key=lambda result: result.match_score, reverse=True)

    logger.info("search_notes returned %d result(s)", len(results))
    return SearchNotesOutput(results=results)


def _keyword_match_score(note: NoteOut, query: str) -> float:
    """
    A simple, explainable relevance score: a match in the title counts
    for more than a match in the body, since the title is a stronger
    signal of what the note is actually about.
    """
    query_lower = query.lower()
    score = 0.0

    if query_lower in note.title.lower():
        score += 0.7
    if query_lower in note.content.lower():
        score += 0.3

    return min(score, 1.0)


# ============================================================
# TOOL 6: SAVE NOTE
# ============================================================

SAVE_NOTE_REQUIRES_APPROVAL = False  # saving a note is low-risk and reversible via deletion


def save_note(data: NoteCreate) -> NoteOut:
    """Save a new note and return it."""
    logger.info("save_note called: title=%r category=%s", data.title, data.category)
    note = repository.create_note(data)
    logger.info("save_note succeeded: note_id=%s", note.note_id)
    return note
