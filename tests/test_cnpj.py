import pytest

from publiceye.core.models import TargetType
from publiceye.core.provider import ProviderContext, is_valid_cnpj
from publiceye.providers import cnpj as cnpj_mod

SAMPLE = {
    "cnpj": "11222333000181",
    "razao_social": "EMPRESA EXEMPLO LTDA",
    "nome_fantasia": "EXEMPLO",
    "descricao_situacao_cadastral": "ATIVA",
    "data_inicio_atividade": "2000-01-01",
    "natureza_juridica": "Sociedade Empresária Limitada",
    "porte": "DEMAIS",
    "capital_social": 100000.0,
    "cnae_fiscal": 6201501,
    "cnae_fiscal_descricao": "Desenvolvimento de programas de computador",
    "logradouro": "AVENIDA PAULISTA",
    "numero": "1000",
    "complemento": "SALA 1",
    "bairro": "BELA VISTA",
    "municipio": "SAO PAULO",
    "uf": "SP",
    "cep": "01310100",
    "email": "contato@exemplo.com.br",
    "ddd_telefone_1": "1130000000",
    "qsa": [
        {"nome_socio": "FULANO DE TAL", "qualificacao_socio": "Sócio-Administrador"}
    ],
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
            cnpj_mod, "HttpClient", lambda ctx, min_interval=0.5: _FakeHttp(payload)
        )

    return _apply


async def test_cnpj_parses_fields(patch_http):
    patch_http(SAMPLE)
    findings = await cnpj_mod.CnpjProvider().run(
        "11.222.333/0001-81", ProviderContext()
    )
    kinds = {f.kind: f.value for f in findings}
    assert kinds["cnpj:razao_social"] == "EMPRESA EXEMPLO LTDA"
    assert kinds["cnpj:nome_fantasia"] == "EXEMPLO"
    assert kinds["cnpj:situacao"] == "ATIVA"
    assert kinds["cnpj:cnae"] == "6201501 - Desenvolvimento de programas de computador"
    assert kinds["cnpj:endereco"] == (
        "AVENIDA PAULISTA, 1000, SALA 1, BELA VISTA, SAO PAULO, SP"
    )
    assert kinds["cnpj:socio:Sócio-Administrador"] == "FULANO DE TAL"


async def test_cnpj_skips_invalid(patch_http):
    patch_http(SAMPLE)
    findings = await cnpj_mod.CnpjProvider().run(
        "11.222.333/0001-80", ProviderContext()
    )
    assert findings == []


def test_cnpj_only_supports_cnpj():
    assert cnpj_mod.CnpjProvider.supports(TargetType.CNPJ)
    assert not cnpj_mod.CnpjProvider.supports(TargetType.DOMAIN)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("11.222.333/0001-81", True),
        ("11222333000181", True),
        ("11.222.333/0001-80", False),
        ("11111111111111", False),
        ("123", False),
    ],
)
def test_is_valid_cnpj(value, expected):
    assert is_valid_cnpj(value) is expected
