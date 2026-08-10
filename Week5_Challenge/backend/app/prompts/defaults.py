"""Starter prompts seeded into every new workspace's Prompt Library, so it isn't an
empty page on day one. Users can edit or delete these freely — they're just a starting point.
"""

DEFAULT_PROMPTS = [
    {
        "name": "Explain like I'm new to this",
        "category": "education",
        "content": (
            "Explain the following topic in plain language, as if I'm encountering it for the "
            "first time. Use a concrete example.\n\nTopic: "
        ),
    },
    {
        "name": "Code review",
        "category": "programming",
        "content": (
            "Review the following code for correctness, readability, and potential bugs. "
            "Be specific and suggest concrete fixes.\n\n```\n\n```"
        ),
    },
    {
        "name": "Tighten this writing",
        "category": "writing",
        "content": "Rewrite the following text to be clearer and more concise without losing meaning:\n\n",
    },
    {
        "name": "Research questions",
        "category": "research",
        "content": (
            "Given the following topic, list the most important open questions a researcher "
            "should investigate first, and why each matters.\n\nTopic: "
        ),
    },
]
