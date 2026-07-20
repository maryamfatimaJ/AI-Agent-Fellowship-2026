# Execution Limits

Requirement 9 asks for these limits to be documented, with reasoning —
not just declared. All three are configured in `config.py` via
environment variables, with the values below as defaults.

## Maximum agent steps: 8

Set in `MAX_AGENT_STEPS`, enforced in `agent/graph.py`'s main decision
loop.

**Why 8:** every one of this app's workflows is short by design.
Even the most involved one — Meeting Notes → Tasks — only needs two
real tool calls (extract the action items, then propose the tasks),
plus the decision step before each one. Daily Planning and Weekly
Review are similar: two or three tool calls, then an answer. Eight
steps gives comfortable headroom above any legitimate workflow (roughly
2-3x what's actually needed) without leaving enough room for a
misbehaving model to run up a large number of Gemini API calls (and
cost) on a single user request before something stops it.

## Maximum retries per tool: 2

Set in `MAX_TOOL_RETRIES`, enforced in `agent/nodes.py`'s
`execute_tool_with_limits()` (so up to 3 total attempts: the original
call plus 2 retries).

**Why 2:** the tools in this app are either pure database operations
(SQLite, typically fails immediately and consistently if it's going to
fail at all, e.g. bad input, missing record) or a single LLM/API call
(Extract Meeting Actions). Retrying a handful of times gives a genuine
transient failure — a brief network hiccup or a momentary Gemini
rate-limit — a real chance to succeed on retry, without silently
retrying an already-doomed call so many times that the user sits
waiting for an error that was inevitable from the first attempt.

## Tool timeout: 30 seconds

Set in `TOOL_TIMEOUT_SECONDS`, enforced in `agent/nodes.py` using a
worker-thread timeout around each tool call.

**Why 30 seconds:** database operations in this app complete in
milliseconds — 30 seconds is not tuned for them, it's tuned for the one
tool that calls out to an external API under the hood (Extract Meeting
Actions, via Gemini). A typical Gemini response for a single
transcript-extraction request is well under this, so this limit is
essentially never expected to trigger in normal use — it exists purely
as a hard backstop against the app hanging indefinitely if Google's API
becomes unresponsive, rather than as a limit that's expected to bind
in practice.

## Duplicate-call detection and loop prevention

Not a numeric limit, but enforced the same way: `agent/graph.py` tracks
every `(tool_name, arguments)` pair already called in the current run.
If the model tries to call the exact same tool with the exact same
arguments twice in one run, the loop stops immediately with a clear
error, rather than letting a confused model spin through its full step
budget repeating an unproductive call. This is tested directly in
`tests/test_agent.py::test_duplicate_tool_call_is_stopped`.

## A related, code-level safeguard (Requirement 7)

Requirement 7 requires approval before creating *multiple* tasks. A
single `create_task` call doesn't need approval, but nothing would
otherwise stop the model from just calling `create_task` several times
in a row, one approval-free call at a time — a silent way around that
rule. `agent/graph.py` closes this at the code level: if `create_task`
is called a **second** time in the same run, approval is forced
regardless of the tool's normal setting. The intended path for
creating several tasks at once is the dedicated `create_tasks_bulk`
tool, which always requires approval. Both behaviors are tested in
`tests/test_agent.py::test_second_create_task_call_forces_approval`.
