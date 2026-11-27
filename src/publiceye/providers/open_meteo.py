"""Provider: Open-Meteo (clima atual).

API pública e gratuita, sem chave. Aceita coordenadas (`lat,lon`) ou o nome
de um local (resolvido pela API de geocodificação da Open-Meteo).
Docs: https://open-meteo.com/en/docs
"""

from __future__ import annotations

import re

from publiceye.core.models import Confidence, Finding, TargetType
from publiceye.core.provider import Provider, ProviderContext, is_coordinates
from publiceye.core.registry import register
from publiceye.utils.http import HttpClient

_FORECAST = "https://api.open-meteo.com/v1/forecast"
_GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"

# Códigos WMO usados pela Open-Meteo para descrever o tempo.
_WEATHER_CODES = {
    0: "Céu limpo",
    1: "Principalmente limpo",
    2: "Parcialmente nublado",
    3: "Nublado",
    45: "Nevoeiro",
    48: "Nevoeiro com geada",
    51: "Chuvisco leve",
    53: "Chuvisco moderado",
    55: "Chuvisco intenso",
    56: "Chuvisco congelante leve",
    57: "Chuvisco congelante intenso",
    61: "Chuva leve",
    63: "Chuva moderada",
    65: "Chuva intensa",
    66: "Chuva congelante leve",
    67: "Chuva congelante intensa",
    71: "Neve leve",
    73: "Neve moderada",
    75: "Neve intensa",
    77: "Grãos de neve",
    80: "Pancadas de chuva leves",
    81: "Pancadas de chuva moderadas",
    82: "Pancadas de chuva intensas",
    85: "Pancadas de neve leves",
    86: "Pancadas de neve intensas",
    95: "Trovoada",
    96: "Trovoada com granizo leve",
    99: "Trovoada com granizo intenso",
}

_COORD_INPUT = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


@register
class OpenMeteoProvider(Provider):
    name = "open-meteo"
    description = "Clima atual por coordenadas ou cidade (Open-Meteo, sem chave)."
    target_types = (TargetType.WEATHER,)

    async def run(self, target: str, ctx: ProviderContext) -> list[Finding]:
        async with HttpClient(ctx, min_interval=1.0) as http:
            lat, lon, label = await _resolve_location(http, target)
            data = await http.get_json(
                _FORECAST,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": (
                        "temperature_2m,relative_humidity_2m,"
                        "apparent_temperature,precipitation,"
                        "weather_code,wind_speed_10m"
                    ),
                    "timezone": "auto",
                },
            )

        current = data.get("current") or {}
        units = data.get("current_units") or {}
        if not current:
            return []

        findings: list[Finding] = []

        def add(kind: str, value: object, unit: str = "") -> None:
            if value in (None, ""):
                return
            text = f"{value} {unit}".strip() if unit else str(value)
            findings.append(
                Finding(
                    source=self.name,
                    kind=kind,
                    value=text,
                    confidence=Confidence.HIGH,
                )
            )

        add("weather:local", f"{label} ({lat}, {lon})")
        add("weather:time", current.get("time"))
        add("weather:timezone", data.get("timezone"), "")

        for kind, key in (
            ("weather:temperature", "temperature_2m"),
            ("weather:apparent_temperature", "apparent_temperature"),
            ("weather:humidity", "relative_humidity_2m"),
            ("weather:precipitation", "precipitation"),
            ("weather:wind_speed", "wind_speed_10m"),
        ):
            add(kind, current.get(key), units.get(key, ""))

        code = current.get("weather_code")
        if code is not None:
            description = _WEATHER_CODES.get(int(code), f"Código WMO {code}")
            add("weather:condition", f"{description} ({code})")

        return findings


async def _resolve_location(
    http: HttpClient, target: str
) -> tuple[float, float, str]:
    """Devolve (lat, lon, rótulo); geocodifica se o alvo não for coordenadas."""
    if is_coordinates(target):
        match = _COORD_INPUT.match(target)
        assert match is not None
        lat, lon = float(match.group(1)), float(match.group(2))
        return lat, lon, "coordenadas"

    data = await http.get_json(
        _GEOCODE,
        params={"name": target.strip(), "count": 1, "language": "pt", "format": "json"},
    )
    results = data.get("results") or []
    if not results:
        raise ValueError(f"Local não encontrado: {target!r}")

    place = results[0]
    label = place.get("name") or target
    admin = place.get("admin1")
    country = place.get("country")
    if admin:
        label = f"{label}, {admin}"
    if country:
        label = f"{label}, {country}"
    return float(place["latitude"]), float(place["longitude"]), label
