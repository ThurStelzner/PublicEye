"""Provider: Nominatim / OpenStreetMap (geocodificação e reversa).

Serviço público e gratuito de geocodificação. Devolve coordenadas e endereço
estruturado a partir de um texto (busca direta) ou o endereço de um ponto
(geocodificação reversa, quando o alvo é `lat,lon`).

Uso ético obrigatório: 1 requisição/segundo no máximo e User-Agent
identificável — ambos já aplicados aqui. Docs/ToS:
https://nominatim.org/release-docs/latest/api/Overview/
"""

from __future__ import annotations

from publiceye.core.models import Confidence, Finding, TargetType
from publiceye.core.provider import (
    Provider,
    ProviderContext,
    parse_coordinates,
)
from publiceye.core.registry import register
from publiceye.utils.http import HttpClient

_BASE = "https://nominatim.openstreetmap.org"
_LANG = "pt-BR,pt,en"

# Componentes de endereço que vale a pena expor como achados próprios.
_ADDRESS_KEYS = (
    "house_number",
    "road",
    "neighbourhood",
    "suburb",
    "city",
    "town",
    "village",
    "municipality",
    "state",
    "postcode",
    "country",
    "country_code",
)


@register
class NominatimProvider(Provider):
    name = "nominatim"
    description = "Geocodificação direta e reversa de endereços (Nominatim/OSM)."
    target_types = (TargetType.PLACE,)

    async def run(self, target: str, ctx: ProviderContext) -> list[Finding]:
        coords = parse_coordinates(target)
        async with HttpClient(ctx, min_interval=1.0) as http:
            if coords:
                data = await http.get_json(
                    f"{_BASE}/reverse",
                    params={
                        "lat": coords[0],
                        "lon": coords[1],
                        "format": "jsonv2",
                        "addressdetails": 1,
                        "accept-language": _LANG,
                    },
                )
                places = [data] if isinstance(data, dict) else []
                mode = "reverse"
            else:
                data = await http.get_json(
                    f"{_BASE}/search",
                    params={
                        "q": target.strip(),
                        "format": "jsonv2",
                        "addressdetails": 1,
                        "limit": 1,
                        "accept-language": _LANG,
                    },
                )
                places = data if isinstance(data, list) else []
                mode = "forward"

        if not places:
            return []

        place = places[0] or {}
        findings: list[Finding] = []

        def add(kind: str, value: object, confidence: Confidence) -> None:
            if value not in (None, ""):
                findings.append(
                    Finding(
                        source=self.name,
                        kind=kind,
                        value=str(value),
                        confidence=confidence,
                    )
                )

        add("geocode:mode", mode, Confidence.HIGH)
        add("geocode:display_name", place.get("display_name"), Confidence.HIGH)
        add("geocode:lat", place.get("lat"), Confidence.HIGH)
        add("geocode:lon", place.get("lon"), Confidence.HIGH)
        add("geocode:osm_type", place.get("osm_type"), Confidence.HIGH)
        add("geocode:osm_id", place.get("osm_id"), Confidence.HIGH)
        add("geocode:category", place.get("class"), Confidence.MEDIUM)
        add("geocode:type", place.get("type"), Confidence.MEDIUM)
        add("geocode:importance", place.get("importance"), Confidence.LOW)

        bbox = place.get("boundingbox")
        if bbox:
            add("geocode:boundingbox", ",".join(str(b) for b in bbox), Confidence.MEDIUM)

        address = place.get("address") or {}
        for key in _ADDRESS_KEYS:
            if address.get(key):
                add(f"geocode:address:{key}", address[key], Confidence.HIGH)

        return findings
