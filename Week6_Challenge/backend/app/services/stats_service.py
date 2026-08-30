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
            "cost": {"total_usd": 0.0, "per_request_usd": 0.0, "per_successful_task_usd": None},
            "tokens": {"total": 0, "input": 0, "output": 0},
            "by_model": {},
            "by_trace_type": {},
            "by_prompt_version": {},
            "reliability": {"retry_rate": None, "timeout_rate": None, "error_rate": None, "degraded_rate": None},
            "bottlenecks": [],
        }

    latencies = [t.latency_ms for t in traces]
    total_cost = sum(t.cost_usd for t in traces)
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

    n = len(traces)
    return {
        "n_requests": n,
        "successful_requests": len(successful),
        "failed_requests": len(failed),
        "latency_ms": _latency_percentiles(latencies),
        "cost": {
            "total_usd": round(total_cost, 6),
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
    }
