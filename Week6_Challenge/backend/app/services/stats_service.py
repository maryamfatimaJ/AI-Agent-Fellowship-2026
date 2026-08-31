"""Cost and performance aggregation over the traces table — the single
source of truth populated by every LLM/RAG/memory/skill/agent call (see
trace_service.record_trace). Backs the Quality Dashboard's Performance tab
and the evaluation baseline/optimization reports.
"""

from datetime import datetime

import numpy as np
from sqlalchemy.orm import Session

from app.models.trace import Trace, TraceStatus


def _latency_percentiles(latencies: list[float]) -> dict:
    if not latencies:
        return {"mean": None, "median": None, "p50": None, "p95": None, "p99": None}
    arr = np.array(latencies)
    return {
        "mean": round(float(np.mean(arr)), 2),
        "median": round(float(np.median(arr)), 2),
        "p50": round(float(np.percentile(arr, 50)), 2),
        "p95": round(float(np.percentile(arr, 95)), 2),
        "p99": round(float(np.percentile(arr, 99)), 2),
    }


def _meta_stage_latencies(traces: list[Trace], meta_key: str) -> list[float]:
    """Pulls one sub-stage timing (e.g. "llm_ms"/"rag_ms"/"db_ms", set by
    chat_service.py/orchestrator.py alongside the trace's own end-to-end
    latency_ms) out of each trace's meta JSON, skipping traces that never
    recorded that stage (e.g. a tool_call trace has no "rag_ms")."""
    return [t.meta[meta_key] for t in traces if isinstance((t.meta or {}).get(meta_key), (int, float))]


def _span_stage_latencies(traces: list[Trace], span_name: str) -> list[float]:
    """Pulls every span's duration_ms matching `span_name` out of every
    trace's meta.spans timeline — used for stages that can occur more than
    once per trace (a multi-step agent turn has one "tool_result" span per
    tool call), unlike the single-value meta keys _meta_stage_latencies reads."""
    durations = []
    for t in traces:
        for span in (t.meta or {}).get("spans") or []:
            if span.get("name") == span_name and isinstance(span.get("duration_ms"), (int, float)):
                durations.append(span["duration_ms"])
    return durations


def get_performance_summary(
    workspace_id: str,
    db: Session,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    model: str | None = None,
) -> dict:
    """`since`/`until`/`model` are optional breakdown filters (Quality Dashboard
    date-range and model filters) — omitted, this aggregates every trace the
    workspace has ever produced, exactly as before these filters existed."""
    query = db.query(Trace).filter(Trace.workspace_id == workspace_id)
    if since is not None:
        query = query.filter(Trace.created_at >= since)
    if until is not None:
        query = query.filter(Trace.created_at <= until)
    if model is not None:
        query = query.filter(Trace.model == model)
    traces = query.all()
    if not traces:
        return {
            "n_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "latency_ms": _latency_percentiles([]),
            "cost": {
                "total_usd": 0.0,
                "input_usd": 0.0,
                "output_usd": 0.0,
                "per_request_usd": 0.0,
                "per_successful_task_usd": None,
            },
            "tokens": {"total": 0, "input": 0, "output": 0},
            "by_model": {},
            "by_trace_type": {},
            "by_prompt_version": {},
            "reliability": {"retry_rate": None, "timeout_rate": None, "error_rate": None, "degraded_rate": None},
            "bottlenecks": [],
            "latency_by_stage": {
                "llm_ms": _latency_percentiles([]),
                "retrieval_ms": _latency_percentiles([]),
                "tool_ms": _latency_percentiles([]),
                "database_ms": _latency_percentiles([]),
                "end_to_end_ms": _latency_percentiles([]),
            },
            "bottleneck_stage": None,
        }

    latencies = [t.latency_ms for t in traces]
    total_cost = sum(t.cost_usd for t in traces)
    # input_cost_usd/output_cost_usd are nullable (added after cost_usd existed —
    # see app/models/trace.py) so traces recorded before this column existed
    # contribute 0 to these sums rather than raising on a None + float add.
    total_input_cost = sum(t.input_cost_usd or 0.0 for t in traces)
    total_output_cost = sum(t.output_cost_usd or 0.0 for t in traces)
    successful = [t for t in traces if t.status in (TraceStatus.SUCCESS, TraceStatus.RETRIED)]
    failed = [t for t in traces if t.status in (TraceStatus.ERROR, TraceStatus.TIMEOUT)]

    by_model: dict[str, dict] = {}
    for t in traces:
        key = t.model or "unknown"
        bucket = by_model.setdefault(key, {"n_requests": 0, "total_cost_usd": 0.0, "total_tokens": 0})
        bucket["n_requests"] += 1
        bucket["total_cost_usd"] += t.cost_usd
        bucket["total_tokens"] += t.input_tokens + t.output_tokens
    for bucket in by_model.values():
        bucket["total_cost_usd"] = round(bucket["total_cost_usd"], 6)

    by_prompt_version: dict[str, dict] = {}
    for t in traces:
        key = (t.meta or {}).get("prompt_version") or "unversioned"
        bucket = by_prompt_version.setdefault(key, {"n_requests": 0, "n_successful": 0, "avg_latency_ms": []})
        bucket["n_requests"] += 1
        if t.status in (TraceStatus.SUCCESS, TraceStatus.RETRIED):
            bucket["n_successful"] += 1
        bucket["avg_latency_ms"].append(t.latency_ms)
    for bucket in by_prompt_version.values():
        bucket["avg_latency_ms"] = round(sum(bucket["avg_latency_ms"]) / len(bucket["avg_latency_ms"]), 2)
        bucket["success_rate"] = round(bucket["n_successful"] / bucket["n_requests"], 3)

    # "Cost by feature" (Week 6 cost-tracking requirement) — trace_type is this
    # app's feature axis (chat/skill/tool_call/embedding/memory_extraction);
    # there is no separate "cost by agent" breakdown since this is a
    # single-agent system (tool_call traces already are the one agent's cost).
    by_type: dict[str, dict] = {}
    for t in traces:
        key = t.trace_type.value
        bucket = by_type.setdefault(key, {"n_requests": 0, "avg_latency_ms": [], "total_cost_usd": 0.0})
        bucket["n_requests"] += 1
        bucket["avg_latency_ms"].append(t.latency_ms)
        bucket["total_cost_usd"] += t.cost_usd
    bottlenecks = []
    for key, bucket in by_type.items():
        avg_latency = sum(bucket["avg_latency_ms"]) / len(bucket["avg_latency_ms"])
        bucket["avg_latency_ms"] = round(avg_latency, 2)
        bucket["total_cost_usd"] = round(bucket["total_cost_usd"], 6)
        bottlenecks.append({"stage": key, "avg_latency_ms": bucket["avg_latency_ms"], "n_requests": bucket["n_requests"]})
    bottlenecks.sort(key=lambda b: b["avg_latency_ms"], reverse=True)

    # Latency Analysis (Week 6 requirement): full mean/median/P50/P95/P99 per
    # pipeline stage, not just an average-per-trace-type — LLM/retrieval/tool
    # come from meta/spans recorded by chat_service.py and orchestrator.py;
    # database is the two message-persistence commits chat_service.py times
    # (see Trace.meta["db_ms"]); end_to_end mirrors the top-level `latency_ms`
    # above, included here so every stage — including the whole request — is
    # comparable side by side for bottleneck identification.
    latency_by_stage = {
        "llm_ms": _latency_percentiles(_meta_stage_latencies(traces, "llm_ms")),
        "retrieval_ms": _latency_percentiles(_meta_stage_latencies(traces, "rag_ms")),
        "tool_ms": _latency_percentiles(_span_stage_latencies(traces, "tool_result")),
        "database_ms": _latency_percentiles(_meta_stage_latencies(traces, "db_ms")),
        "end_to_end_ms": _latency_percentiles(latencies),
    }
    bottleneck_stage = max(
        (stage for stage, stats in latency_by_stage.items() if stage != "end_to_end_ms" and stats["mean"] is not None),
        key=lambda stage: latency_by_stage[stage]["mean"],
        default=None,
    )

    n = len(traces)
    return {
        "n_requests": n,
        "successful_requests": len(successful),
        "failed_requests": len(failed),
        "latency_ms": _latency_percentiles(latencies),
        "cost": {
            "total_usd": round(total_cost, 6),
            "input_usd": round(total_input_cost, 6),
            "output_usd": round(total_output_cost, 6),
            "per_request_usd": round(total_cost / n, 6) if n else 0.0,
            # None (not 0.0) when there are zero successful tasks — an undefined
            # ratio must never render as "free", see docs/quality-dashboard.md.
            "per_successful_task_usd": round(total_cost / len(successful), 6) if successful else None,
        },
        "tokens": {
            "total": sum(t.input_tokens + t.output_tokens for t in traces),
            "input": sum(t.input_tokens for t in traces),
            "output": sum(t.output_tokens for t in traces),
        },
        "by_model": by_model,
        "by_trace_type": by_type,
        "by_prompt_version": by_prompt_version,
        "reliability": {
            "retry_rate": round(sum(1 for t in traces if t.retry_count > 0) / n, 3),
            "timeout_rate": round(sum(1 for t in traces if t.status == TraceStatus.TIMEOUT) / n, 3),
            "error_rate": round(sum(1 for t in traces if t.status == TraceStatus.ERROR) / n, 3),
            "degraded_rate": round(sum(1 for t in traces if t.status == TraceStatus.DEGRADED) / n, 3),
        },
        "bottlenecks": bottlenecks[:5],
        "latency_by_stage": latency_by_stage,
        "bottleneck_stage": bottleneck_stage,
    }
