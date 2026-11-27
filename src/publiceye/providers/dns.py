"""Provider: DNS público via DNS over HTTPS (DoH).

Consulta registros DNS por HTTPS usando o resolvedor público do Google
(`dns.google`), sem chave de API. Para domínios devolve registros A, AAAA,
MX, NS, TXT e CNAME; para IPs faz a consulta reversa (PTR).
O resultado é o que o resolvedor tem em cache — pode divergir por alguns
instantes do servidor autoritativo (TTL).
Docs: https://developers.google.com/speed/public-dns/docs/doh/json
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any

from publiceye.core.models import Confidence, Finding, TargetType
from publiceye.core.provider import Provider, ProviderContext
from publiceye.core.registry import register
from publiceye.utils.http import HttpClient

_BASE = "https://dns.google/resolve"
_TYPES = ("A", "AAAA", "MX", "NS", "TXT", "CNAME")
_TYPE_NAMES = {1: "A", 2: "NS", 5: "CNAME", 6: "SOA", 12: "PTR", 15: "MX", 16: "TXT", 28: "AAAA"}

# Nomes DNS não distinguem maiúsculas; normaliza para evitar duplicatas.
_HOST_TYPES = {"NS", "CNAME", "PTR"}


@register
class DnsProvider(Provider):
    name = "dns"
    description = "Registros DNS públicos via DNS over HTTPS (dns.google)."
    target_types = (TargetType.DOMAIN, TargetType.IP)

    async def run(self, target: str, ctx: ProviderContext) -> list[Finding]:
        findings: list[Finding] = []
        seen: set[tuple[str, str]] = set()

        async with HttpClient(ctx, min_interval=0.5) as http:
            reverse = _reverse_name(target)
            if reverse is not None:
                await _query(http, self.name, reverse, "PTR", findings, seen)
            else:
                domain = target.strip().lower().rstrip(".")
                for qtype in _TYPES:
                    await _query(http, self.name, domain, qtype, findings, seen)

        return findings


async def _query(
    http: HttpClient,
    source: str,
    name: str,
    qtype: str,
    findings: list[Finding],
    seen: set[tuple[str, str]],
) -> None:
    data = await http.get_json(
        _BASE,
        params={"name": name, "type": qtype},
        headers={"Accept": "application/dns-json"},
    )
    if not isinstance(data, dict) or data.get("Status") != 0:
        return  # NXDOMAIN, SERVFAIL ou resposta inesperada: nada a reportar.

    for answer in data.get("Answer") or []:
        if not isinstance(answer, dict):
            continue
        rtype = _TYPE_NAMES.get(answer.get("type"), qtype)
        value = _format_value(rtype, answer.get("data"))
        if value is None:
            continue
        key = (rtype.lower(), value)
        if key in seen:
            continue
        seen.add(key)
        findings.append(
            Finding(
                source=source,
                kind=f"dns:{rtype.lower()}",
                value=value,
                confidence=Confidence.HIGH,
                data={"type": rtype, "ttl": answer.get("TTL")},
            )
        )


def _format_value(rtype: str, data: Any) -> str | None:
    if data in (None, ""):
        return None
    text = str(data).strip()

    if rtype == "TXT":
        chunks = re.findall(r'"([^"]*)"', text)
        return "".join(chunks).strip() or None

    if rtype == "MX":
        # "10 mail.example.com." -> "10 mail.example.com"
        priority, _, host = text.partition(" ")
        return f"{priority} {host.rstrip('.').lower()}".strip()

    if rtype in _HOST_TYPES:
        return text.rstrip(".").lower()

    return text


def _reverse_name(target: str) -> str | None:
    """Nome PTR (`...in-addr.arpa`) para um IP; None se o alvo não for IP."""
    try:
        return ipaddress.ip_address(target.strip()).reverse_pointer
    except ValueError:
        return None
