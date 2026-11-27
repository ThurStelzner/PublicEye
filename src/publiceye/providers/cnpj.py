"""Provider: CNPJ (dados públicos de empresa) via BrasilAPI.

Fonte pública brasileira, sem chave de API. A BrasilAPI espelha os dados
abertos da Receita Federal (Cadastro Nacional da Pessoa Jurídica): razão
social, nome fantasia, situação cadastral, CNAE, endereço e quadro de sócios.
Docs: https://brasilapi.com.br/docs
"""

from __future__ import annotations

from publiceye.core.models import Confidence, Finding, TargetType
from publiceye.core.provider import Provider, ProviderContext, is_valid_cnpj
from publiceye.core.registry import register
from publiceye.utils.http import HttpClient


@register
class CnpjProvider(Provider):
    name = "cnpj"
    description = "Dados públicos de empresa a partir do CNPJ (BrasilAPI/Receita)."
    target_types = (TargetType.CNPJ,)

    async def run(self, target: str, ctx: ProviderContext) -> list[Finding]:
        cnpj = "".join(ch for ch in target if ch.isdigit())
        if not is_valid_cnpj(cnpj):
            return []

        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
        async with HttpClient(ctx, min_interval=0.5) as http:
            data = await http.get_json(url)

        if not isinstance(data, dict):
            return []

        findings: list[Finding] = []

        def add(kind: str, value: object, confidence: Confidence) -> None:
            if value not in (None, "", 0):
                findings.append(
                    Finding(
                        source=self.name,
                        kind=kind,
                        value=str(value),
                        confidence=confidence,
                    )
                )

        add("cnpj:razao_social", data.get("razao_social"), Confidence.HIGH)
        add("cnpj:nome_fantasia", data.get("nome_fantasia"), Confidence.HIGH)
        add(
            "cnpj:situacao",
            data.get("descricao_situacao_cadastral") or data.get("situacao_cadastral"),
            Confidence.HIGH,
        )
        add("cnpj:data_abertura", data.get("data_inicio_atividade"), Confidence.HIGH)
        add("cnpj:natureza_juridica", data.get("natureza_juridica"), Confidence.HIGH)
        add("cnpj:porte", data.get("porte"), Confidence.MEDIUM)
        add("cnpj:capital_social", data.get("capital_social"), Confidence.MEDIUM)

        cnae = data.get("cnae_fiscal")
        cnae_desc = data.get("cnae_fiscal_descricao")
        if cnae:
            add("cnpj:cnae", f"{cnae} - {cnae_desc}" if cnae_desc else cnae, Confidence.HIGH)

        address = _format_address(data)
        add("cnpj:endereco", address, Confidence.HIGH)
        add("cnpj:municipio", data.get("municipio"), Confidence.HIGH)
        add("cnpj:uf", data.get("uf"), Confidence.HIGH)
        add("cnpj:cep", data.get("cep"), Confidence.HIGH)

        add("cnpj:email", data.get("email"), Confidence.MEDIUM)
        phone = data.get("ddd_telefone_1")
        add("cnpj:telefone", phone, Confidence.MEDIUM)

        for socio in data.get("qsa", []) or []:
            if isinstance(socio, dict):
                name = socio.get("nome_socio")
                role = socio.get("qualificacao_socio")
                if name:
                    add(
                        f"cnpj:socio:{role}" if role else "cnpj:socio",
                        name,
                        Confidence.MEDIUM,
                    )

        return findings


def _format_address(data: dict) -> str | None:
    """Monta o endereço completo a partir dos campos soltos da BrasilAPI."""
    parts = [
        data.get("logradouro"),
        data.get("numero"),
        data.get("complemento"),
        data.get("bairro"),
        data.get("municipio"),
        data.get("uf"),
    ]
    clean = [str(p).strip() for p in parts if p not in (None, "")]
    return ", ".join(clean) or None
