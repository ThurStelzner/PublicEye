import pytest

from publiceye.core.models import TargetType
from publiceye.core.provider import ProviderContext
from publiceye.providers import geoip as geoip_mod

SAMPLE = {
    "ip": "8.8.8.8",
    "success": True,
    "country": "United States",
    "country_code": "US",
    "region": "California",
    "city": "San Jose",
    "latitude": 37.3393939,
    "longitude": -121.8949553,
    "timezone": {"id": "America/Los_Angeles"},
    "connection": {"asn": 15169, "org": "Google LLC", "isp": "Google LLC"},
}


class _FakeHttp:
    def __init__(self, payload):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def get_json(self, url, **kwargs):
        return self._payload


@pytest.fixture
def patch_http(monkeypatch):
    def _apply(payload):
        monkeypatch.setattr(
            geoip_mod, "HttpClient", lambda ctx, min_interval=0.5: _FakeHttp(payload)
        )

    return _apply


async def test_geoip_parses_fields(patch_http):
    patch_http(SAMPLE)
    findings = await geoip_mod.GeoIpProvider().run("8.8.8.8", ProviderContext())
    kinds = {f.kind: f.value for f in findings}
    assert kinds["asn"] == "15169"
    assert kinds["isp"] == "Google LLC"
    assert kinds["geo:country"] == "United States (US)"
    assert kinds["geo:city"] == "San Jose"


async def test_geoip_unsuccessful_returns_empty(patch_http):
    patch_http({"success": False, "message": "reserved range"})
    findings = await geoip_mod.GeoIpProvider().run("10.0.0.1", ProviderContext())
    assert findings == []


def test_geoip_only_supports_ip():
    assert geoip_mod.GeoIpProvider.supports(TargetType.IP)
    assert not geoip_mod.GeoIpProvider.supports(TargetType.DOMAIN)
