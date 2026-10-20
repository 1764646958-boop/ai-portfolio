from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ComparisonStatus = Literal[
    "increase",
    "decrease",
    "unchanged",
    "pending_baseline",
    "new_item",
    "missing_quote",
]


class StandardListVersionResponse(BaseModel):
    id: int
    version_name: str
    original_filename: str
    file_hash: str
    item_count: int
    created_at: datetime


class ComparisonSummary(BaseModel):
    total: int = 0
    changed: int = 0
    increase: int = 0
    decrease: int = 0
    unchanged: int = 0
    pending_baseline: int = 0
    new_item: int = 0
    missing_quote: int = 0


class ComparisonItem(BaseModel):
    row: int
    sequence: str
    name: str
    description: str
    unit: str
    baseline_price: str | None = None
    quoted_price: str | None = None
    difference: str | None = None
    percentage: str | None = None
    status: ComparisonStatus
    status_label: str


class QuoteComparisonListItem(BaseModel):
    id: int
    standard_version_id: int
    standard_version_name: str
    original_filename: str
    summary: ComparisonSummary
    created_at: datetime


class QuoteComparisonResponse(QuoteComparisonListItem):
    items: list[ComparisonItem]
