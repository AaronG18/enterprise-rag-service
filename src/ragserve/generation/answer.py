"""Answer value object."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Answer:
    text: str
    citations: List[str] = field(default_factory=list)
    refused: bool = False
    reason_code: Optional[str] = None     # no_context | out_of_scope | low_confidence | safety_trigger | injection_detected
    guidance: str = ""
    confidence: float = 0.0
    usage: Dict[str, int] = field(default_factory=dict)
    provider: str = "deterministic"
    model_version: str = "stub-deterministic-1"

    def to_dict(self) -> Dict:
        return {
            "text": self.text,
            "citations": list(self.citations),
            "refused": self.refused,
            "reason_code": self.reason_code,
            "guidance": self.guidance,
            "confidence": round(self.confidence, 4),
            "usage": dict(self.usage),
            "provider": self.provider,
            "model_version": self.model_version,
        }
