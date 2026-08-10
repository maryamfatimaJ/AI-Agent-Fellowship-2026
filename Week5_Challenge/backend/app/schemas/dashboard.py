from datetime import datetime

from pydantic import BaseModel


class DashboardCounts(BaseModel):
    conversations: int
    messages: int
    documents: int
    memory_items: int
    prompt_templates: int
    skills: int


class DashboardUsage(BaseModel):
    total_input_tokens: int
    total_output_tokens: int
    estimated_cost_usd: float


class ActivityItem(BaseModel):
    type: str
    title: str
    timestamp: datetime


class DashboardRead(BaseModel):
    counts: DashboardCounts
    usage: DashboardUsage
    recent_activity: list[ActivityItem]
