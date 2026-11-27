import pytest

from publiceye.core.models import TargetType
from publiceye.core.provider import ProviderContext
from publiceye.providers import open_meteo as om_mod

FORECAST = {
    "latitude": -23.55,
    "longitude": -46.63,
    "timezone": "America/Sao_Paulo",
    "current": {
        "time": "2026-11-27T12:00",
        "temperature_2m": 25.3,
        "relative_humidity_2m": 60,
        "apparent_temperature": 26.1,
        "precipitation": 0.0,
        "weather_code": 2,
        "wind_speed_10m": 11.2,
    },
    "current_units": {
        "temperature_2m": "°C",
        "relative_humidity_2m": "%",
        "apparent_temperature": "°C",
        "precipitation": "mm",
        "wind_speed_10m": "km/h",
    },
}

GEOCODE = {
    "results": [
        {
            "name": "São Paulo",
            "admin1": "São Paulo",
            "country": "Brasil",
            "latitude": -23.55,
            "longitude": -46.63,
        }
    ]
}


class _FakeHttp:
    def __init__(self, forecast, geocode=None):
        self._forecast = forecast
        self._geocode = geocode

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def get_json(self, url, **kwargs):
        if "geocoding-api" in url:
            return self._geocode
        return self._forecast


@pytest.fixture
def patch_http(monkeypatch):
    def _apply(forecast, geocode=None):
        monkeypatch.setattr(
            om_mod,
            "HttpClient",
            lambda ctx, min_interval=1.0: _FakeHttp(forecast, geocode),
        )

    return _apply


async def test_weather_parses_current(patch_http):
    patch_http(FORECAST)
    findings = await om_mod.OpenMeteoProvider().run("-23.55,-46.63", ProviderContext())
    kinds = {f.kind: f.value for f in findings}
    assert kinds["weather:temperature"] == "25.3 °C"
    assert kinds["weather:apparent_temperature"] == "26.1 °C"
    assert kinds["weather:humidity"] == "60 %"
    assert kinds["weather:condition"] == "Parcialmente nublado (2)"
    assert kinds["weather:timezone"] == "America/Sao_Paulo"


async def test_weather_geocodes_city(patch_http):
    patch_http(FORECAST, GEOCODE)
    findings = await om_mod.OpenMeteoProvider().run("São Paulo", ProviderContext())
    kinds = {f.kind: f.value for f in findings}
    assert "São Paulo" in kinds["weather:local"]
    assert kinds["weather:temperature"] == "25.3 °C"


async def test_weather_unknown_place_raises(patch_http):
    patch_http(FORECAST, {"results": []})
    with pytest.raises(ValueError):
        await om_mod.OpenMeteoProvider().run("Lugar Inexistente", ProviderContext())


def test_weather_only_supports_weather():
    assert om_mod.OpenMeteoProvider.supports(TargetType.WEATHER)
    assert not om_mod.OpenMeteoProvider.supports(TargetType.DOMAIN)
