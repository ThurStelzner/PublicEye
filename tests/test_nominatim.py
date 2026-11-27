import pytest

from publiceye.core.models import TargetType
from publiceye.core.provider import ProviderContext
from publiceye.providers import nominatim as nom_mod

FORWARD = [
    {
        "place_id": 123,
        "osm_type": "way",
        "osm_id": 456,
        "lat": "-23.561414",
        "lon": "-46.655881",
        "display_name": "Avenida Paulista, Bela Vista, São Paulo, SP, Brasil",
        "class": "highway",
        "type": "primary",
        "importance": 0.8,
        "boundingbox": ["-23.57", "-23.55", "-46.67", "-46.64"],
        "address": {
            "road": "Avenida Paulista",
            "suburb": "Bela Vista",
            "city": "São Paulo",
            "state": "São Paulo",
            "postcode": "01310-100",
            "country": "Brasil",
            "country_code": "br",
        },
    }
]

REVERSE = {
    "place_id": 789,
    "osm_type": "node",
    "osm_id": 321,
    "lat": "-23.561414",
    "lon": "-46.655881",
    "display_name": "Avenida Paulista, Bela Vista, São Paulo, SP, Brasil",
    "address": {
        "road": "Avenida Paulista",
        "house_number": "1578",
        "city": "São Paulo",
        "state": "São Paulo",
        "country": "Brasil",
        "country_code": "br",
    },
}


class _FakeHttp:
    def __init__(self, forward, reverse):
        self._forward = forward
        self._reverse = reverse

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def get_json(self, url, **kwargs):
        if url.endswith("/reverse"):
            return self._reverse
        return self._forward


@pytest.fixture
def patch_http(monkeypatch):
    def _apply(forward=FORWARD, reverse=REVERSE):
        monkeypatch.setattr(
            nom_mod,
            "HttpClient",
            lambda ctx, min_interval=1.0: _FakeHttp(forward, reverse),
        )

    return _apply


async def test_geocode_forward(patch_http):
    patch_http()
    findings = await nom_mod.NominatimProvider().run(
        "Avenida Paulista, São Paulo", ProviderContext()
    )
    kinds = {f.kind: f.value for f in findings}
    assert kinds["geocode:mode"] == "forward"
    assert kinds["geocode:lat"] == "-23.561414"
    assert kinds["geocode:address:road"] == "Avenida Paulista"
    assert kinds["geocode:address:city"] == "São Paulo"
    assert kinds["geocode:address:country_code"] == "br"


async def test_geocode_reverse_with_coordinates(patch_http):
    patch_http()
    findings = await nom_mod.NominatimProvider().run(
        "-23.561414,-46.655881", ProviderContext()
    )
    kinds = {f.kind: f.value for f in findings}
    assert kinds["geocode:mode"] == "reverse"
    assert kinds["geocode:address:house_number"] == "1578"
    assert kinds["geocode:osm_type"] == "node"


async def test_geocode_not_found_returns_empty(patch_http):
    patch_http(forward=[])
    findings = await nom_mod.NominatimProvider().run(
        "lugar inexistente", ProviderContext()
    )
    assert findings == []


def test_nominatim_only_supports_place():
    assert nom_mod.NominatimProvider.supports(TargetType.PLACE)
    assert not nom_mod.NominatimProvider.supports(TargetType.DOMAIN)
