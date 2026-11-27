import pytest

from publiceye.core.models import TargetType
from publiceye.core.provider import ProviderContext
from publiceye.providers import dns as dns_mod


class FakeHttp:
    """Substitui HttpClient devolvendo respostas DoH por tipo de consulta."""

    def __init__(self, responses):
        self._responses = responses
        self.calls: list[tuple[str, str]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def get_json(self, url, params=None, headers=None, **kwargs):
        self.calls.append((params["name"], params["type"]))
        return self._responses.get(params["type"], {"Status": 3})


DOMAIN_RESPONSES = {
    "A": {
        "Status": 0,
        "Answer": [
            {"name": "example.com.", "type": 1, "TTL": 300, "data": "93.184.216.34"}
        ],
    },
    "AAAA": {
        "Status": 0,
        "Answer": [
            {
                "name": "example.com.",
                "type": 28,
                "TTL": 300,
                "data": "2606:2800:220:1:248:1893:25c8:1946",
            }
        ],
    },
    "MX": {
        "Status": 0,
        "Answer": [{"name": "example.com.", "type": 15, "TTL": 300, "data": "10 mail.example.com."}],
    },
    "NS": {
        "Status": 0,
        "Answer": [{"name": "example.com.", "type": 2, "TTL": 172800, "data": "a.iana-servers.net."}],
    },
    "TXT": {
        "Status": 0,
        "Answer": [{"name": "example.com.", "type": 16, "TTL": 300, "data": '"v=spf1 -all"'}],
    },
    "CNAME": {"Status": 0},
}


@pytest.fixture
def fake_http(monkeypatch):
    def _apply(responses):
        fake = FakeHttp(responses)
        monkeypatch.setattr(
            dns_mod, "HttpClient", lambda ctx, min_interval=0.5: fake
        )
        return fake

    return _apply


async def test_dns_parses_domain_records(fake_http):
    fake = fake_http(DOMAIN_RESPONSES)
    findings = await dns_mod.DnsProvider().run("Example.com", ProviderContext())
    got = {f.kind: f.value for f in findings}

    assert got["dns:a"] == "93.184.216.34"
    assert got["dns:aaaa"] == "2606:2800:220:1:248:1893:25c8:1946"
    assert got["dns:mx"] == "10 mail.example.com"
    assert got["dns:ns"] == "a.iana-servers.net"
    assert got["dns:txt"] == "v=spf1 -all"
    assert "dns:cname" not in got

    # Consulta o domínio normalizado, cada tipo uma vez.
    assert fake.calls == [("example.com", t) for t in dns_mod._TYPES]


async def test_dns_nxdomain_returns_nothing(fake_http):
    fake_http({})
    findings = await dns_mod.DnsProvider().run("naoexiste.example", ProviderContext())
    assert findings == []


async def test_dns_reverse_lookup_for_ip(fake_http):
    fake = fake_http(
        {
            "PTR": {
                "Status": 0,
                "Answer": [{"name": "8.8.8.8.in-addr.arpa.", "type": 12, "TTL": 60, "data": "dns.google."}],
            }
        }
    )
    findings = await dns_mod.DnsProvider().run("8.8.8.8", ProviderContext())
    got = {f.kind: f.value for f in findings}

    assert got["dns:ptr"] == "dns.google"
    assert fake.calls == [("8.8.8.8.in-addr.arpa", "PTR")]


def test_dns_supports_domain_and_ip():
    assert dns_mod.DnsProvider.supports(TargetType.DOMAIN)
    assert dns_mod.DnsProvider.supports(TargetType.IP)
    assert not dns_mod.DnsProvider.supports(TargetType.CEP)
