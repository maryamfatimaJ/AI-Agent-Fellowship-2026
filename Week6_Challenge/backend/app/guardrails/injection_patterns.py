"""Heuristic prompt-injection detection, shared by input_guard (scans user
messages — direct injection) and chat_service's RAG-context assembly (scans
retrieved document chunks before they're placed in the prompt — indirect
injection). Duck-typed regex, not an LLM classifier: cheap, deterministic,
and good enough to catch the common attack shapes covered by
tests/security/test_prompt_injection.py.
"""

import re

PATTERNS: dict[str, re.Pattern] = {
    "ignore_instructions": re.compile(r"\bignore\b.{0,30}\b(instructions|rules|prompt|guidelines)\b", re.I),
    "disregard_instructions": re.compile(r"\bdisregard\b.{0,30}\b(instructions|rules|guidelines)\b", re.I),
    "forget_instructions": re.compile(r"\bforget\b.{0,30}\b(you were told|instructions|above|before)\b", re.I),
    "override_rules": re.compile(r"\boverride\b.{0,20}\b(rules|guidelines|programming|instructions)\b", re.I),
    "new_instructions_marker": re.compile(r"\bnew instructions?\s*:", re.I),
    "system_prompt_reveal": re.compile(
        r"(reveal|print|show|repeat|leak|what is) (your |the )?(system prompt|initial instructions|hidden prompt)",
        re.I,
    ),
    "role_override": re.compile(r"\byou are now\b|\bact as\b|\bpretend (you are|to be)\b", re.I),
    "developer_mode": re.compile(r"developer mode|jailbreak|\bDAN\b|do anything now", re.I),
    "fake_system_tag": re.compile(r"^\s*\[?system\]?\s*:", re.I | re.M),
    "end_of_prompt_marker": re.compile(r"end of (system )?(prompt|instructions)", re.I),
    "instruction_injection_in_data": re.compile(
        r"(assistant|ai)[,:]? (please )?(now )?(do|execute|run|perform) the following", re.I
    ),
    "credential_exfiltration": re.compile(r"(reveal|leak|print|show) (the )?(api key|secret key|password|credentials)", re.I),
    "prompt_leak_request": re.compile(r"repeat (the )?(text|words|instructions) above", re.I),
    "encoded_instruction_hint": re.compile(r"\bdecode\b.{0,30}\b(follow|execute|run)\b", re.I),
    "long_base64_blob": re.compile(r"[A-Za-z0-9+/]{80,}={0,2}"),
    "html_comment_injection": re.compile(r"<!--\s*(system|instruction|ignore)", re.I),
    "safety_bypass_directive": re.compile(
        r"\b(disable|skip|bypass|turn off)\b.{0,40}\b(safety|security|approval|permission)\b", re.I
    ),
}


def scan_for_injection(text: str) -> list[str]:
    if not text:
        return []
    return [name for name, pattern in PATTERNS.items() if pattern.search(text)]
