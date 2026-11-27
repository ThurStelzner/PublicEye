"""Base de um Provider (fonte pública) e seu contexto de execução."""

from __future__ import annotations

import abc
import re
from dataclasses import dataclass, field

from publiceye.core.models import Finding, TargetType

DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$", re.IGNORECASE
)
IPV4_RE = re.compile(
    r"^(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)$"
)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CEP_RE = re.compile(r"^\d{5}-?\d{3}$")


def detect_target_type(target: str) -> TargetType:
    """Classifica o alvo sem adivinhar: só o formato observável."""
    t = target.strip().lower()
    if EMAIL_RE.match(t):
        return TargetType.EMAIL
    if IPV4_RE.match(t):
        return TargetType.IP
    if CEP_RE.match(t):
        return TargetType.CEP
    if DOMAIN_RE.match(t):
        return TargetType.DOMAIN
    return TargetType.UNKNOWN


@dataclass
class ProviderContext:
    """Configuração passada a cada provider em tempo de execução."""

    timeout: float = 30.0
    user_agent: str = "PublicEye/0.1 (+https://github.com/ThurStelzner/PublicEye)"
    options: dict = field(default_factory=dict)


class Provider(abc.ABC):
    """Contrato de uma fonte de dados pública.

    Todo provider DEVE consultar apenas fontes públicas/legais e respeitar
    termos de uso e limites de taxa do serviço.
    """

    name: str = "unnamed"
    description: str = ""
    target_types: tuple[TargetType, ...] = ()

    @classmethod
    def supports(cls, target_type: TargetType) -> bool:
        return not cls.target_types or target_type in cls.target_types

    @abc.abstractmethod
    async def run(self, target: str, ctx: ProviderContext) -> list[Finding]:
        """Executa a coleta e devolve zero ou mais findings."""
        raise NotImplementedError
