import pytest

from publiceye.core.models import Confidence, TargetType
from publiceye.core.provider import ProviderContext
from publiceye.providers import whois as whois_mod

IANA_DOMAIN = """
% IANA WHOIS server
% for more information on IANA, visit http://www.iana.org
whois:        whois.registry.test
status:       ACTIVE
"""

REGISTRY_DOMAIN = """
   Domain Name: EXAMPLE.COM
   Registrar: Example Registrar, Inc.
   Creation Date: 1995-08-14T04:00:00Z
   Updated Date: 2026-01-01T00:00:00Z
   Registry Expiry Date: 2027-08-13T04:00:00Z
   Name Server: A.IANA-SERVERS.NET.
   Name Server: B.IANA-SERVERS.NET.
   Domain Status: clientTransferProhibited https://icann.org/epp#clientTransferProhibited
   Registrant Organization: REDACTED FOR PRIVACY
   DNSSEC: signedDelegation
For more information on Whois status codes, please visit https://icann.org/epp
"""

IANA_IP = """
% IANA WHOIS server
refer:        whois.rir.test
"""

RIR_IP = """
NetName:        GOGL
Organization:   Google LLC (GOGL)
OrgName:        Google LLC
Country:        US
OrgAbuseEmail:  network-abuse@google.com
"""


@pytest.fixture
def fake_query(monkeypatch):
    def _apply(responses):
        calls: list[tuple[str, str]] = []

        async def _query(host, query, timeout):
            calls.append((host, query))
            return responses.get(host, "")

        monkeypatch.setattr(whois_mod, "_query", _query)
        monkeypatch.setattr(whois_mod, "_DELAY", 0)
        return calls

    return _apply


async def test_whois_parses_domain_registry(fake_query):
    calls = fake_query({"whois.iana.org": IANA_DOMAIN, "whois.registry.test": REGISTRY_DOMAIN})
    findings = await whois_mod.WhoisProvider().run("Example.com", ProviderContext())
    got = {f.kind: f.value for f in findings}

    assert got["whois:domain"] == "EXAMPLE.COM"
    assert got["whois:registrar"] == "Example Registrar, Inc."
    assert got["whois:created"] == "1995-08-14T04:00:00Z"
    assert got["whois:updated"] == "2026-01-01T00:00:00Z"
    assert got["whois:expires"] == "2027-08-13T04:00:00Z"
    assert got["whois:nameserver"] in {"a.iana-servers.net", "b.iana-servers.net"}
    assert got["whois:status"] == "clientTransferProhibited"
    assert got["whois:dnssec"] == "signedDelegation"
    # Dado pessoal redigido é descartado.
    assert "whois:registrant" not in got
    # Prosa com ":" não vira achado.
    assert not any("icann" in f.value for f in findings)

    assert calls == [("whois.iana.org", "example.com"), ("whois.registry.test", "example.com")]


async def test_whois_parses_ip_registry(fake_query):
    fake_query({"whois.iana.org": IANA_IP, "whois.rir.test": RIR_IP})
    findings = await whois_mod.WhoisProvider().run("8.8.8.8", ProviderContext())
    got = {f.kind: f.value for f in findings}

    assert got["whois:netname"] == "GOGL"
    assert got["whois:country"] == "US"
    assert got["whois:abuse_email"] == "network-abuse@google.com"
    abuse = next(f for f in findings if f.kind == "whois:abuse_email")
    assert abuse.confidence is Confidence.MEDIUM


async def test_whois_not_found_returns_nothing(fake_query):
    fake_query({"whois.iana.org": IANA_DOMAIN, "whois.registry.test": "No match for EXAMPLE.INVALID."})
    findings = await whois_mod.WhoisProvider().run("example.invalid", ProviderContext())
    assert findings == []


async def test_whois_without_referral_returns_nothing(fake_query):
    fake_query({"whois.iana.org": "% sem referência\nstatus: ACTIVE\n"})
    findings = await whois_mod.WhoisProvider().run("example.com", ProviderContext())
    assert findings == []


def test_whois_supports_domain_and_ip():
    assert whois_mod.WhoisProvider.supports(TargetType.DOMAIN)
    assert whois_mod.WhoisProvider.supports(TargetType.IP)
    assert not whois_mod.WhoisProvider.supports(TargetType.CEP)


def test_referral_extracts_host_with_port():
    assert whois_mod._referral("ReferralServer: whois://whois.ripe.net:43\n") == "whois.ripe.net"
