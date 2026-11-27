"""Modelos de dados: alvo, achado (finding) e relatório."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum


class Confidence(str, Enum):
    """Quão confiável é o achado — sempre explícito."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TargetType(str, Enum):
    DOMAIN = "domain"
    IP = "ip"
    EMAIL = "email"
    CEP = "cep"
    CNPJ = "cnpj"
    UNKNOWN = "unknown"


@dataclass
class Finding:
    """Um dado coletado de uma fonte pública."""

    source: str
    kind: str
    value: str
    confidence: Confidence = Confidence.MEDIUM
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["confidence"] = self.confidence.value
        return d


@dataclass
class ProviderError:
    source: str
    error: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Report:
    target: str
    target_type: str
    findings: list[Finding] = field(default_factory=list)
    errors: list[ProviderError] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "target_type": self.target_type,
            "generated_at": self.generated_at,
            "count": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
            "errors": [e.to_dict() for e in self.errors],
        }
