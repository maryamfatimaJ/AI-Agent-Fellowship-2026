"""Seed data for the six default skills every new workspace gets. Each skill is just a
name + category + a prompt_template — the execution engine in skill_service.py is generic
and reads this config at run time, so adding a 7th skill later is a data change, not a
new endpoint.
"""

DEFAULT_SKILLS = [
    {
        "name": "Summarize",
        "category": "writing",
        "description": "Condense a conversation, document excerpt, or pasted text into key points.",
        "prompt_template": (
            "Summarize the following text or conversation clearly and concisely. "
            "Preserve the key points, decisions, and any action items. Use short paragraphs "
            "or a bulleted list, whichever fits the content better."
        ),
    },
    {
        "name": "Write an email",
        "category": "business",
        "description": "Turn rough notes or instructions into a professional email.",
        "prompt_template": (
            "Write a clear, professional email based on the following context or instructions. "
            "Include a subject line. Match a tone appropriate to the context (formal unless "
            "the input suggests otherwise)."
        ),
    },
    {
        "name": "Generate a report",
        "category": "business",
        "description": "Turn notes or findings into a structured report with headings.",
        "prompt_template": (
            "Turn the following notes or information into a structured report. Include a short "
            "executive summary, clear section headings, and a conclusion. Use markdown headings."
        ),
    },
    {
        "name": "Meeting notes",
        "category": "business",
        "description": "Turn a raw transcript or rough notes into structured meeting notes.",
        "prompt_template": (
            "Turn the following raw meeting transcript or notes into structured meeting notes. "
            "Include: attendees (if mentioned), key discussion points, decisions made, and a "
            "clearly separated list of action items with owners if mentioned."
        ),
    },
    {
        "name": "Generate ideas",
        "category": "research",
        "description": "Brainstorm a diverse, practical list of ideas from a prompt or context.",
        "prompt_template": (
            "Generate a diverse list of creative, practical ideas based on the following prompt "
            "or context. Number them, and give each a one-sentence justification for why it "
            "could work."
        ),
    },
    {
        "name": "SWOT analysis",
        "category": "business",
        "description": "Structured Strengths/Weaknesses/Opportunities/Threats analysis.",
        "prompt_template": (
            "Perform a SWOT analysis (Strengths, Weaknesses, Opportunities, Threats) based on "
            "the following business, product, or situation description. Structure your answer "
            "under those four headings, with 2-4 bullet points each."
        ),
    },
]
