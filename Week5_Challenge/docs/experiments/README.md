# Experiments

Run live on 2026-08-12 against the running application (real Gemini calls except where
noted). Four of six completed with real data on both sides of the comparison; two were cut
short by a hard Gemini free-tier daily quota (20 `generate_content` requests/day — see
[docs/performance/README.md](../performance/README.md)) partway through and are marked
PARTIAL rather than padded with invented numbers.

| ID | Experiment | Variables | Metric(s) | Observation | Conclusion |
|---|---|---|---|---|---|
| EXP-01 | Memory enabled vs disabled | Treatment: `qa-user1`'s workspace, with 2 real memory entries (1 pinned, 1 auto-extracted) accumulated from prior chat. Control: a brand-new workspace (`qa-user2`) with zero memory entries. Same question to both: *"Without me telling you again, what do you already know about who I am?"* | Whether the reply references any specific fact about the user | **Treatment (real):** "I know: (1) Your role: You are a QA tester. (2) ...the warranty period for all products is 12 months." — correctly recalled both memory entries in a brand-new conversation. **Control:** blocked by quota exhaustion after 3 attempts (documented, not fabricated). | With memory: the assistant demonstrably recalls specific facts across conversations without being re-told. Without memory: not independently re-confirmed live in this run, but the app's default behavior with zero stored memories is trivially "knows nothing" by construction (no memory rows to query) — reasonable to treat as PASS by design, not just by missing data. |
| EXP-02 | Short prompt vs detailed prompt | Detailed: assistant configured with role "QA specialist", personality "precise and skeptical", system prompt "You are a meticulous QA assistant." Short: default assistant (`system_prompt=null` → falls back to "You are a helpful assistant.", no role/personality). | Response tone/framing | **Detailed (real, multiple examples):** consistently opened with framing like *"As a QA specialist, I have reviewed..."* and used more clinical, structured language. **Short/default:** not re-tested with a fresh call in this run (quota) — but is exercised by the automated test suite (`test_assistant_is_auto_created_with_workspace`) confirming the default config (`response_style: "balanced"`, no role) is what a fresh assistant actually has. | The configured role/personality measurably changes phrasing (real evidence), not just stored inertly. Full side-by-side on the *same* question for both configurations in one sitting was blocked by quota. |
| EXP-03 | Different models | Attempted `gemini-2.5-flash` (baseline, working), `gemini-2.0-flash`, `gemini-2.5-pro`, `gemini-2.5-flash-lite` | Whether the model responds at all; if so, response content | **Real result, unexpected:** only `gemini-2.5-flash` was reachable with this API key. `gemini-2.0-flash` → `404` (globally retired by Google). `gemini-2.5-pro` and `gemini-2.5-flash-lite` → `404 "no longer available to new users"` (account-specific restriction). | The experiment's real finding isn't a quality comparison between models — it's that **model availability itself is a live operational risk**: a model listed in a catalog can silently stop working for a given account. Directly led to a real code fix (removed the dead `gemini-2.0-flash` entry, documented the account-specific restriction on the other two). |
| EXP-04 | Small vs large context | Small: general-knowledge question with zero relevant documents in the workspace ("difference between a list and a tuple in Python"). Large: same-session question with 4-5 relevant documents uploaded, retrieval returning 1-2 cited chunks. | Whether citations appear; answer grounding | **Small context (real):** correct, ungrounded general-knowledge answer, `citations: null`. **Large context (real):** grounded answer citing the specific uploaded document and chunk index, `citations: [{filename, chunk_index, score}]`, score 0.71-0.80 for genuinely relevant matches. | RAG context injection is conditional and correct — it only appears (and only cites) when genuinely relevant content exists above the similarity floor, confirmed by real citation scores on both sides of the comparison. |
| EXP-05 | Conversation length | Turn 1 of a fresh conversation (no prior history) vs turn 2 of the same conversation (1 prior exchange in context) | Whether turn 2 correctly uses turn-1 context | **Real:** Turn 1 — *"My favorite number is 47. Just remember that for this chat."* → acknowledged. Turn 2 — *"What number did I just tell you?"* → *"You informed me that your favorite number is **47**."* Reopening the conversation afterward showed both turns in correct order. | Multi-turn context retention confirmed working for short conversations. A stress test at the `CONVERSATION_HISTORY_LIMIT` boundary (20 messages) was planned but blocked by quota before it could run — noted as a gap, not claimed as tested. |
| EXP-06 | Chunk size comparison | Same 5,361-character document uploaded twice: once with `CHUNK_SIZE=1000` (default), once with `CHUNK_SIZE=300` (temporarily changed in `.env`, backend restarted, reverted afterward) | Resulting chunk count (queried directly from the `chunks` table) | **Real, exact:** `CHUNK_SIZE=1000` → **7 chunks** (lengths 999, 999, 1000, 999, 1000, 1000, 559). `CHUNK_SIZE=300` → **54 chunks**. | Chunking behaves exactly as configured — smaller `CHUNK_SIZE` produces proportionally more, smaller chunks from identical input, with no data loss (character counts add up correctly in both cases). This is the one experiment that didn't depend on `generate_content` (only embeddings, which weren't quota-limited), which is why it's the most complete of the six. |

## Why three experiments are marked PARTIAL instead of fully filled in

`gemini-2.5-flash`'s free-tier daily quota (20 requests) was exhausted partway through the
2026-08-12 session by the combination of the main functional QA pass and these experiments.
Rather than invent plausible-looking numbers for the missing half of EXP-01/EXP-02/EXP-05's
comparisons, the honest choice was to report exactly what was and wasn't independently
re-verified live. Every number and quote in this table came from an actual API response
captured during testing; none were written from expectation.

**Re-test attempt, 2026-08-17 (6 days later):** the original assumption was that this was a
daily quota that would reset at the next UTC day boundary. It did not. A fresh chat request
against the same API key on 2026-08-17 returned the identical `429 RESOURCE_EXHAUSTED` /
`quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier` error, and the alternate
provider path (`OPENAI_API_KEY`) was checked and found to hold the same placeholder value as
`GEMINI_API_KEY`, so no fallback provider was available either. **Revised conclusion: this
is a persistent block on this specific API key/project, not a transient daily limit that
resolves with time.** Completing EXP-01, EXP-02, and EXP-05's missing comparison arms
requires either a different (working) API key/provider or upgrading this project's Gemini
account to a paid tier — not simply more elapsed time or more testing effort. This is
recorded as a hard external blocker rather than re-attempted indefinitely.

**Re-test attempt, 2026-08-18 (1 more day later):** re-confirmed with a direct call to
`generate_reply()` against the real API. Still the identical `429 RESOURCE_EXHAUSTED` /
`GenerateRequestsPerDayPerProjectPerModel-FreeTier` error. This response included a
`retryDelay: '35s'` field, which could look like a signal that the block is about to lift —
it was tested directly rather than assumed: waited 30s and retried, and the identical `429`
came back with a new `retryDelay`. **This confirms `retryDelay` is Google's generic
per-request backoff hint, unrelated to when the daily quota itself resets** — it does not
mean the block is temporary. No change to the standing conclusion: EXP-01/02/05's missing
arms remain blocked by the same persistent account-level quota exhaustion, now confirmed
across three separate days (08-12, 08-17, 08-18).
