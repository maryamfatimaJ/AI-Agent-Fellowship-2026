"""Shared enums used across schemas, state, agents, and the API layer."""

from __future__ import annotations

from enum import StrEnum


class AgentName(StrEnum):
    SUPERVISOR = "supervisor"
    RESEARCH = "research"
    ANALYST = "analyst"
    CRITIC = "critic"
    WRITER = "writer"
    FACT_CHECKER = "fact_checker"
    RISK_ANALYST = "risk_analyst"
    COMPETITOR_ANALYSIS = "competitor_analysis"
    STRATEGY = "strategy"
    HUMAN = "human"


class WorkflowStatus(StrEnum):
    RECEIVED = "received"
    ANALYZING_REQUEST = "analyzing_request"
    AWAITING_CLARIFICATION = "awaiting_clarification"
    PLANNING = "planning"
    RESEARCHING = "researching"
    STORING_EVIDENCE = "storing_evidence"
    ANALYZING = "analyzing"
    CRITIQUING = "critiquing"
    REVISING = "revising"
    WRITING_REPORT = "writing_report"
    AWAITING_APPROVAL = "awaiting_approval"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EvidenceType(StrEnum):
    FACT = "fact"
    CLAIM = "claim"
    ASSUMPTION = "assumption"
    MISSING_INFORMATION = "missing_information"


class CriticVerdict(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class LogLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    TOOL = "tool"


class HandoffType(StrEnum):
    RESEARCH_TO_ANALYST = "research_to_analyst"
    ANALYST_TO_CRITIC = "analyst_to_critic"
    CRITIC_TO_SUPERVISOR = "critic_to_supervisor"
    SUPERVISOR_TO_WRITER = "supervisor_to_writer"
