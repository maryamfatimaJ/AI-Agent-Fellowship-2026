"""CSV Reader Tool — reads user-supplied CSV data (e.g. an internal metrics
export) into a list of row dicts for the Analyst/Research agents to cite."""

from __future__ import annotations

import csv
import io

from app.utils.errors import ToolExecutionError


def read_csv_text(csv_text: str, *, max_rows: int = 500) -> list[dict[str, str]]:
    """Parse CSV text (already read into memory) into row dictionaries."""

    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        rows = []
        for i, row in enumerate(reader):
            if i >= max_rows:
                break
            rows.append(dict(row))
        return rows
    except csv.Error as exc:
        raise ToolExecutionError("Failed to parse CSV content", details={"error": str(exc)}) from exc


def read_csv_file(path: str, *, max_rows: int = 500) -> list[dict[str, str]]:
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            return read_csv_text(handle.read(), max_rows=max_rows)
    except OSError as exc:
        raise ToolExecutionError(f"Could not open CSV file: {path}", details={"error": str(exc)}) from exc
