# Part 3 — Skills, Prompt Library, Dashboard & Advanced Features

**Date:** 2026-08-10

## Decisions made and why

- **Skills as one generic execution engine, not six endpoints.** Each skill is a DB row
  (`name`, `category`, `config.prompt_template`). `skill_service.run_skill()` reads that
  config at run time. Adding a 7th skill is a data seed change, not new code — satisfies
  "don't simply create six hardcoded buttons."
- **Skill output becomes real conversation messages when attached to a conversation.**
  Chosen over a side-channel "skill result" concept so skills genuinely integrate with
  existing chat history, search, export, and pinning instead of being an isolated feature.
- **Token usage tracking added centrally, not per-feature.** `llm_service.generate_reply`
  now returns a `GenerationResult(text, input_tokens, output_tokens)` instead of a bare
  string; `usage_service.record_usage()` is called from chat, memory extraction, and
  skills alike, so the dashboard's totals are real across every LLM-calling code path,
  not just chat.
- **"Assistant invokes skills naturally" interpreted as user-triggered, not autonomous
  tool-calling.** Skills are reachable from the chat composer and the Skills page, and the
  underlying model is generally capable of doing the same task in plain conversation
  (e.g., "do a SWOT analysis of X" just works without the discrete skill machinery).
  Full LLM function-calling to let the assistant decide when to invoke a skill was scoped
  out as a bigger, riskier change than the time available justified.
- **Multi-model support surfaced via a real catalog, not free text.** A small static
  `/api/models` catalog backs a dropdown in the assistant settings UI; the underlying
  provider-agnostic generation path already existed from Part 2, so this was mostly a UX
  fix, not new plumbing.
- **Dark mode as a manual toggle, not just `prefers-color-scheme`.** The color tokens
  already existed as CSS custom properties from Part 2; added `:root[data-theme]`
  overrides plus a `ThemeContext` so the choice persists in `localStorage` and beats the
  OS setting when the user picks one explicitly.

## Real bug found and fixed during live testing

RAG was injecting document context into the prompt for every chat turn regardless of
relevance, which visibly confused a reply to an unrelated message. Fixed with a cosine
similarity floor (`RAG_MIN_SCORE`). See [part-2.md](part-2.md) — the fix landed while
testing Part 2 functionality again after the Part 3 refactor, not new to this part.

## Known limitations for Part 4

- Usage/cost figures are estimates from a hardcoded pricing table, not billing-accurate.
- No automated frontend/browser test — no headless browser tool is available in this
  environment; verified via build success, type-checking, and live API-level testing.
- Skill invocation is explicit (user-picked), not autonomous LLM tool-calling.
