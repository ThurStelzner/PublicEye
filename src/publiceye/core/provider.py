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
CNPJ_RE = re.compile(r"^\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}$")


def is_valid_cnpj(value: str) -> bool:
    """Valida um CNPJ (14 dígitos) pelo algoritmo dos dígitos verificadores."""
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) != 14 or len(set(digits)) == 1:
        return False

    def check_digit(nums: str, weights: list[int]) -> int:
        total = sum(int(n) * w for n, w in zip(nums, weights))
        rest = total % 11
        return 0 if rest < 2 else 11 - rest

    first = check_digit(digits[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    second = check_digit(digits[:13], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return digits[12] == str(first) and digits[13] == str(second)


def detect_target_type(target: str) -> TargetType:
    """Classifica o alvo sem adivinhar: só o formato observável."""
    t = target.strip().lower()
    if EMAIL_RE.match(t):
        return TargetType.EMAIL
    if IPV4_RE.match(t):
        return TargetType.IP
    if CEP_RE.match(t):
        return TargetType.CEP
    if CNPJ_RE.match(t) and is_valid_cnpj(t):
        return TargetType.CNPJ
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
