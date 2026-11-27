"""Provider: RDAP (Registration Data Access Protocol).

Fonte pública oficial de registro de domínios e IPs. O endpoint de bootstrap
`rdap.org` redireciona para o RDAP autoritativo. Não requer chave de API.
Docs: https://about.rdap.org/
"""

from __future__ import annotations

from publiceye.core.models import Confidence, Finding, TargetType
from publiceye.core.provider import Provider, ProviderContext
from publiceye.core.registry import register
from publiceye.utils.http import HttpClient


@register
class RdapProvider(Provider):
    name = "rdap"
    description = "Registro público de domínio/IP via RDAP (bootstrap rdap.org)."
    target_types = (TargetType.DOMAIN, TargetType.IP)

    async def run(self, target: str, ctx: ProviderContext) -> list[Finding]:
        kind = "ip" if _looks_like_ip(target) else "domain"
        url = f"https://rdap.org/{kind}/{target}"
        findings: list[Finding] = []

        async with HttpClient(ctx, min_interval=0.5) as http:
            data = await http.get_json(url)

        handle = data.get("handle")
        if handle:
            findings.append(
                Finding(
                    source=self.name,
                    kind="handle",
                    value=str(handle),
                    confidence=Confidence.HIGH,
                )
            )

        for event in data.get("events", []) or []:
            action = event.get("eventAction")
            date = event.get("eventDate")
            if action and date:
                findings.append(
                    Finding(
                        source=self.name,
                        kind=f"event:{action}",
                        value=date,
                        confidence=Confidence.HIGH,
                    )
                )

        for status in data.get("status", []) or []:
            findings.append(
                Finding(
                    source=self.name,
                    kind="status",
                    value=str(status),
                    confidence=Confidence.HIGH,
                )
            )

        for ns in data.get("nameservers", []) or []:
            ldh = ns.get("ldhName")
            if ldh:
                findings.append(
                    Finding(
                        source=self.name,
                        kind="nameserver",
                        value=ldh.lower(),
                        confidence=Confidence.HIGH,
                    )
                )

        for entity in data.get("entities", []) or []:
            roles = ",".join(entity.get("roles", []) or [])
            vcard = entity.get("vcardArray")
            name = _vcard_name(vcard)
            if name:
                findings.append(
                    Finding(
                        source=self.name,
                        kind=f"entity:{roles or 'unknown'}",
                        value=name,
                        confidence=Confidence.MEDIUM,
                    )
                )

        return findings


def _looks_like_ip(value: str) -> bool:
    parts = value.split(".")
    return len(parts) == 4 and all(p.isdigit() for p in parts)


def _vcard_name(vcard: object) -> str | None:
    """Extrai o campo `fn` (nome/razão social) de um vcardArray RDAP."""
    if not isinstance(vcard, list) or len(vcard) < 2:
        return None
    for entry in vcard[1]:
        if isinstance(entry, list) and len(entry) >= 4 and entry[0] == "fn":
            return str(entry[3])
    return None
