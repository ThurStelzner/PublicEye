"""Provider: ViaCEP (CEP → endereço).

Serviço público brasileiro, sem chave de API. Retorna logradouro, bairro,
cidade, UF, código IBGE, DDD e código SIAFI de um CEP.
Docs: https://viacep.com.br/
"""

from __future__ import annotations

from publiceye.core.models import Confidence, Finding, TargetType
from publiceye.core.provider import Provider, ProviderContext
from publiceye.core.registry import register
from publiceye.utils.http import HttpClient


@register
class ViaCepProvider(Provider):
    name = "viacep"
    description = "Endereço a partir de um CEP (viacep.com.br)."
    target_types = (TargetType.CEP,)

    async def run(self, target: str, ctx: ProviderContext) -> list[Finding]:
        cep = "".join(ch for ch in target if ch.isdigit())
        if len(cep) != 8:
            return []

        url = f"https://viacep.com.br/ws/{cep}/json/"
        async with HttpClient(ctx, min_interval=0.5) as http:
            data = await http.get_json(url)

        # ViaCEP sinaliza CEP inexistente com {"erro": true}.
        if not isinstance(data, dict) or data.get("erro"):
            return []

        findings: list[Finding] = []

        def add(kind: str, key: str, confidence: Confidence) -> None:
            value = data.get(key)
            if value:
                findings.append(
                    Finding(
                        source=self.name,
                        kind=kind,
                        value=str(value),
                        confidence=confidence,
                    )
                )

        add("cep:street", "logradouro", Confidence.HIGH)
        add("cep:complement", "complemento", Confidence.HIGH)
        add("cep:district", "bairro", Confidence.HIGH)
        add("cep:city", "localidade", Confidence.HIGH)
        add("cep:state", "uf", Confidence.HIGH)
        add("cep:ibge", "ibge", Confidence.HIGH)
        add("cep:ddd", "ddd", Confidence.HIGH)
        add("cep:siafi", "siafi", Confidence.MEDIUM)

        return findings