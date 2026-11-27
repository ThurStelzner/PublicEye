import asyncio

import pytest

from publiceye.core import fipe as fp


MARCAS = [
    {"codigo": "21", "nome": "Fiat"},
    {"codigo": "23", "nome": "GM - Chevrolet"},
    {"codigo": "59", "nome": "VW - VolksWagen"},
]
MODELOS = {
    "modelos": [
        {"codigo": "1", "nome": "Uno 1.0"},
        {"codigo": "2", "nome": "Palio 1.0"},
    ]
}
ANOS = [
    {"codigo": "2019-1", "nome": "2019 Gasolina"},
    {"codigo": "2020-1", "nome": "2020 Gasolina"},
]
DETAIL = {
    "Valor": "R$ 40.000,00",
    "Marca": "Fiat",
    "Modelo": "Uno 1.0",
    "AnoModelo": 2019,
    "Combustivel": "Gasolina",
    "CodigoFipe": "001000-0",
    "MesReferencia": "novembro de 2025",
    "TipoVeiculo": 1,
}


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


def _search(monkeypatch, payloads, **kwargs):
    monkeypatch.setattr(fp, "HttpClient", lambda ctx, min_interval=0: FakeHttp(payloads))
    return asyncio.run(fp.search_fipe(**kwargs))


def test_search_fipe_full_flow(monkeypatch):
    report = _search(
        monkeypatch,
        [MARCAS, MODELOS, ANOS, DETAIL],
        marca="fiat",
        modelo="uno",
        ano=2019,
    )
    got = {f.kind: f.value for f in report.findings}
    assert got["price"] == "R$ 40.000,00"
    assert got["brand"] == "Fiat"
    assert got["year"] == "2019"
    assert got["code"] == "001000-0"
    assert got["reference"] == "novembro de 2025"


def test_best_match_tolerates_accents_and_partial():
    item = fp._best_match("fiat", MARCAS, "marca")
    assert item["nome"] == "Fiat"


def test_best_match_raises_when_no_match():
    with pytest.raises(ValueError):
        fp._best_match("zzzzzz", MARCAS, "marca")


def test_pick_year_matches_and_errors():
    assert fp._pick_year(ANOS, 2019)["codigo"] == "2019-1"
    with pytest.raises(ValueError):
        fp._pick_year(ANOS, 1999)


def test_pick_year_defaults_to_newest():
    assert fp._pick_year(ANOS, None)["codigo"] == "2020-1"


def test_pick_year_ignores_anomalous_code():
    anos = [{"codigo": "2019-1", "nome": "2019 Flex"}, {"codigo": "32000-1", "nome": "32000 Flex"}]
    assert fp._pick_year(anos, None)["codigo"] == "2019-1"


def test_norm_strips_accents():
    assert fp._norm("VolksWagen") == "volkswagen"
    assert fp._norm("Citroën") == "citroen"