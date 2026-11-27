"""Provider: GeoIP / ASN via ipwho.is.

Serviço público, sem chave de API. Retorna geolocalização **aproximada**
(país/região/cidade), ASN, operadora (ISP) e fuso horário de um IP.
A localização é sempre estimativa — nunca trate como endereço exato.
Docs: https://ipwhois.io/documentation
"""

from __future__ import annotations

from typing import Any

from publiceye.core.models import Confidence, Finding, TargetType
from publiceye.core.provider import Provider, ProviderContext
from publiceye.core.registry import register
from publiceye.utils.http import HttpClient


@register
class GeoIpProvider(Provider):
    name = "geoip"
    description = "Geolocalização aproximada, ASN e operadora de um IP (ipwho.is)."
    target_types = (TargetType.IP,)

    async def run(self, target: str, ctx: ProviderContext) -> list[Finding]:
        url = f"https://ipwho.is/{target}"
        async with HttpClient(ctx, min_interval=0.5) as http:
            data = await http.get_json(url)

        if not isinstance(data, dict) or not data.get("success", False):
            # IP reservado, inválido ou não resolvido: nada a reportar.
            return []

        findings: list[Finding] = []

        def add(kind: str, value: Any, confidence: Confidence) -> None:
            if value not in (None, "", 0):
                findings.append(
                    Finding(
                        source=self.name,
                        kind=kind,
                        value=str(value),
                        confidence=confidence,
                    )
                )

        if data.get("country"):
            add("geo:country", f"{data['country']} ({data.get('country_code', '?')})", Confidence.MEDIUM)
        add("geo:region", data.get("region"), Confidence.LOW)
        add("geo:city", data.get("city"), Confidence.LOW)

        lat, lon = data.get("latitude"), data.get("longitude")
        if lat is not None and lon is not None:
            add("geo:coordinates", f"{lat},{lon}", Confidence.LOW)

        tz = data.get("timezone") or {}
        add("geo:timezone", tz.get("id"), Confidence.MEDIUM)

        conn = data.get("connection") or {}
        add("asn", conn.get("asn"), Confidence.MEDIUM)
        add("org", conn.get("org"), Confidence.MEDIUM)
        add("isp", conn.get("isp"), Confidence.MEDIUM)

        return findings
