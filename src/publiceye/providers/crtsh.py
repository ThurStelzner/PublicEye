"""Provider: Certificate Transparency (crt.sh).

Consulta o log público de certificados TLS. Público, sem chave, e revela
subdomínios emitidos. Docs: https://crt.sh/
"""

from __future__ import annotations

import re
from dataclasses import replace

import httpx

from publiceye.core.models import Confidence, Finding, TargetType
from publiceye.core.provider import Provider, ProviderContext
from publiceye.core.registry import register
from publiceye.utils.http import HttpClient

MAX_SUBDOMAINS = 200

# Hostname válido: labels alfanuméricos/hífen, TLD alfabético.
_HOST_RE = re.compile(
    r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
)


def _is_subdomain_of(name: str, domain: str) -> bool:
    """True só para hostnames reais que terminam em `.domain` (fronteira de ponto)."""
    if not _HOST_RE.match(name):
        return False
    return name.endswith("." + domain.lower())


@register
class CrtshProvider(Provider):
    name = "crtsh"
    description = "Subdomínios a partir do log público de Certificate Transparency (crt.sh)."
    target_types = (TargetType.DOMAIN,)

    async def run(self, target: str, ctx: ProviderContext) -> list[Finding]:
        # crt.sh costuma ser lento e instável; garante folga de tempo sem afetar os demais.
        ctx = replace(ctx, timeout=max(ctx.timeout, 60.0))
        url = f"https://crt.sh/?q=%25.{target}&output=json"
        async with HttpClient(ctx, min_interval=1.0) as http:
            try:
                rows = await http.get_json(
                    url, retries=3, retry_statuses={404, 429, 500, 502, 503, 504}
                )
            except httpx.HTTPStatusError as exc:
                # crt.sh devolve 404 quando não há certificados para a consulta.
                if exc.response.status_code == 404:
                    return []
                raise

        names: set[str] = set()
        issuers: set[str] = set()

        for row in rows or []:
            if not isinstance(row, dict):
                continue
            for name in str(row.get("name_value", "")).splitlines():
                name = name.strip().lower().lstrip("*.")
                if name and _is_subdomain_of(name, target):
                    names.add(name)
            issuer = row.get("issuer_name")
            if issuer and issuer.strip() != "Issuer Not Found":
                issuers.add(issuer.strip())

        findings: list[Finding] = []
        for name in sorted(names)[:MAX_SUBDOMAINS]:
            findings.append(
                Finding(
                    source=self.name,
                    kind="subdomain",
                    value=name,
                    confidence=Confidence.HIGH,
                )
            )
        for issuer in sorted(issuers)[:50]:
            findings.append(
                Finding(
                    source=self.name,
                    kind="issuer",
                    value=issuer,
                    confidence=Confidence.HIGH,
                )
            )
        return findings
