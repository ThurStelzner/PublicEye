import asyncio

import pytest

from publiceye.core import camara as cm
from publiceye.core.provider import ProviderContext


class FakeHttp:
    def __init__(self, payloads):
        self._payloads = list(payloads)
        self._i = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def get_json(self, url, **kwargs):
        p = self._payloads[self._i]
        self._i += 1
        return p


SEARCH_MULTI = {
    "dados": [
        {"id": 1, "nome": "Arthur Lira", "siglaPartido": "PP", "siglaUf": "AL"},
        {"id": 2, "nome": "Arthur Oliveira Maia", "siglaPartido": "UNIÃO", "siglaUf": "BA"},
    ]
}
SEARCH_ONE = {
    "dados": [{"id": 160541, "nome": "Arthur Lira", "siglaPartido": "PP", "siglaUf": "AL"}]
}
DETAIL = {
    "dados": {
        "id": 160541,
        "nomeCivil": "ARTHUR CESAR PEREIRA DA SILVA",
        "cpf": "12345678900",          # NÃO deve aparecer
        "dataNascimento": "1969-06-25",  # NÃO deve aparecer
        "urlWebsite": ["https://arthurlira.com.br"],
        "redeSocial": ["https://twitter.com/arthurlira"],
        "ultimoStatus": {
            "nome": "Arthur Lira",
            "siglaPartido": "PP",
            "siglaUf": "AL",
            "situacao": "Exercício",
            "condicaoEleitoral": "Titular",
            "idLegislatura": 57,
            "email": None,
            "gabinete": {"sala": "17", "predio": "x", "telefone": "3215-5969", "email": "dep.arthurlira@camara.leg.br"},
        },
    }
}


def _run(monkeypatch, payloads, **kwargs):
    monkeypatch.setattr(cm, "HttpClient", lambda ctx, min_interval=0: FakeHttp(payloads))
    return asyncio.run(cm.consultar_deputado(**kwargs))


def test_multi_match_lists_candidates(monkeypatch):
    report = _run(monkeypatch, [SEARCH_MULTI], nome="arthur")
    kinds = [f.kind for f in report.findings]
    assert kinds == ["match", "match"]
    assert report.findings[0].data["id"] == 1


def test_single_match_fetches_detail(monkeypatch):
    report = _run(monkeypatch, [SEARCH_ONE, DETAIL], nome="arthur lira")
    got = {f.kind: f.value for f in report.findings}
    assert got["partido"] == "PP"
    assert got["uf"] == "AL"
    assert got["email"] == "dep.arthurlira@camara.leg.br"
    assert got["telefone"] == "3215-5969"
    assert got["gabinete"] == "sala 17, prédio x"
    assert "https://arthurlira.com.br" in got.get("website", "") or got["website"] == "https://arthurlira.com.br"


def test_never_exposes_personal_data(monkeypatch):
    report = _run(monkeypatch, [SEARCH_ONE, DETAIL], nome="arthur lira")
    blob = " ".join(f"{f.kind}={f.value}" for f in report.findings)
    assert "12345678900" not in blob       # CPF omitido
    assert "1969-06-25" not in blob        # nascimento omitido
    assert "cpf" not in {f.kind for f in report.findings}


def test_by_id_skips_search(monkeypatch):
    report = _run(monkeypatch, [DETAIL], deputado_id=160541)
    assert any(f.kind == "partido" for f in report.findings)


def test_no_match_raises(monkeypatch):
    with pytest.raises(ValueError):
        _run(monkeypatch, [{"dados": []}], nome="zzzzzz")


def test_requires_name_or_id():
    with pytest.raises(ValueError):
        asyncio.run(cm.consultar_deputado())
