"""Structured event log.

Design rules that make the log usable for diagnosis rather than just voluminous:

* **One JSON line per stage**, so a request is a filter, not a grep puzzle.
* **Correlation id on every line** (`workflow_id`), which is what makes single-request
  reconstruction possible - the bar EPIC 8 needs.
* **Redaction at emit time.** A clean answer sitting next to a raw user query in a log line is
  still a leak, so redaction cannot be left to the caller.
* **Injectable clock.** Otherwise no log-related assertion is reproducible (RULES R3).
"""
from __future__ import annotations

import json
import time
from typing import Callable, Dict, List, Optional

from ..generation.pii import redact_record

STAGES = ("request", "retrieval", "decision", "generation", "response")


class EventLog:
    """In-memory sink. Scripts swap in a file sink; tests read `lines()`."""

    def __init__(self):
        self._lines: List[str] = []

    def append(self, line: str) -> None:
        self._lines.append(line)

    def lines(self) -> List[str]:
        return list(self._lines)

    def parsed(self) -> List[Dict]:
        return [json.loads(line) for line in self._lines]

    def for_workflow(self, workflow_id: str) -> List[Dict]:
        return [event for event in self.parsed() if event.get("workflow_id") == workflow_id]


class StructuredLogger:
    def __init__(self, sink: Callable[[str], None], clock: Callable[[], float] = time.time,
                 workflow_id_factory: Optional[Callable[[], str]] = None):
        self.sink = sink
        self.clock = clock
        self._workflow_id_factory = workflow_id_factory
        self._counter = 0

    def new_workflow_id(self) -> str:
        if self._workflow_id_factory:
            return self._workflow_id_factory()
        self._counter += 1
        return "wf-%06d" % self._counter

    def emit(self, stage: str, event: str, workflow_id: str, **fields) -> Dict:
        record = {
            "ts": self.clock(),
            "workflow_id": workflow_id,
            "stage": stage,
            "event": event,
        }
        record.update(fields)
        safe = redact_record(record)
        self.sink(json.dumps(safe, ensure_ascii=False, sort_keys=True))
        return safe
