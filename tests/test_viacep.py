import asyncio

from publiceye.core.provider import ProviderContext
from publiceye.providers import viacep as vc


class FakeHttp:
    def __init__(self, payload):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def get_json(self, url, **kwargs):
        return self._payload


PAYLOAD = {
    "cep": "01310-100",
    "logradouro": "Avenida Paulista",
    "complemento": "de 612 a 1510 - lado par",
    "bairro": "Bela Vista",
    "localidade": "São Paulo",
    "uf": "SP",
    "ibge": "3550308",
    "ddd": "11",
    "siafi": "7107",
}


def _run(monkeypatch, payload):
    monkeypatch.setattr(vc, "HttpClient", lambda ctx, min_interval=0: FakeHttp(payload))
    return asyncio.run(vc.ViaCepProvider().run("01310-100", ProviderContext()))


def test_viacep_extracts_address(monkeypatch):
    findings = _run(monkeypatch, PAYLOAD)
    got = {f.kind: f.value for f in findings}
    assert got["cep:street"] == "Avenida Paulista"
    assert got["cep:city"] == "São Paulo"
    assert got["cep:state"] == "SP"
    assert got["cep:ibge"] == "3550308"


def test_viacep_not_found_returns_nothing(monkeypatch):
    assert _run(monkeypatch, {"erro": True}) == []