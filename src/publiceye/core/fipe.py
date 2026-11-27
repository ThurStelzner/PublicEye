"""Integração com a Tabela FIPE (API pública parallelum.com.br).

FIPE é indexada por marca → modelo → ano, não por placa. Este módulo faz a
busca com *fuzzy matching* de marca/modelo e devolve preço e dados do veículo.
Sem chave de API. Docs: https://deividfortuna.github.io/fipe/
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher

from publiceye.core.models import Confidence, Finding, Report
from publiceye.core.provider import ProviderContext
from publiceye.utils.http import HttpClient

_TIPOS = {"carros", "motos", "caminhoes"}
_BASE = "https://parallelum.com.br/fipe/api/v1"


def _norm(text: str) -> str:
    """Minúsculas e sem acentos, pra comparar nomes."""
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip().lower()


def _score(query: str, candidate: str) -> float:
    q, c = _norm(query), _norm(candidate)
    if not q or not c:
        return 0.0
    if q == c:
        return 1.0
    if c.startswith(q):
        return 0.95
    if q in c:
        return 0.9
    return SequenceMatcher(None, q, c).ratio()


def _best_match(query: str, items: list[dict], label: str) -> dict:
    """Escolhe o item mais parecido; falha com dica se nada passar do limiar."""
    scored = [(_score(query, it.get("nome", "")), it) for it in items]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    if not scored or scored[0][0] < 0.5:
        sample = ", ".join(it.get("nome", "") for it in items[:8])
        raise ValueError(
            f"Nada parecido com {label} {query!r}. Exemplos: {sample}"
        )
    return scored[0][1]


def _candidates(
    query: str, items: list[dict], limit: int = 12, threshold: float = 0.5
) -> list[dict]:
    """Todos os itens plausíveis, do mais parecido pro menos (pra tentar variantes)."""
    scored = [(_score(query, it.get("nome", "")), it) for it in items]
    scored = [pair for pair in scored if pair[0] >= threshold]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [it for _, it in scored[:limit]]


async def search_fipe(
    marca: str,
    modelo: str,
    ano: int | None = None,
    tipo: str = "carros",
    ctx: ProviderContext | None = None,
) -> Report:
    """Consulta a FIPE e devolve um Report com preço e dados do veículo."""
    tipo = tipo.lower()
    if tipo not in _TIPOS:
        raise ValueError(f"tipo inválido {tipo!r}; use: {', '.join(sorted(_TIPOS))}")

    ctx = ctx or ProviderContext()
    report = Report(target=f"{marca} {modelo}" + (f" {ano}" if ano else ""), target_type="vehicle")

    async with HttpClient(ctx, min_interval=0.2) as http:
        marcas = await http.get_json(f"{_BASE}/{tipo}/marcas")
        brand = _best_match(marca, marcas, "marca")

        modelos = (await http.get_json(
            f"{_BASE}/{tipo}/marcas/{brand['codigo']}/modelos"
        )).get("modelos", [])
        model_candidates = _candidates(modelo, modelos, limit=120)
        if not model_candidates:
            sample = ", ".join(m.get("nome", "") for m in modelos[:8])
            raise ValueError(
                f"Nada parecido com modelo {modelo!r}. Exemplos: {sample}"
            )

        chosen: tuple[dict, dict] | None = None
        if ano is None:
            # Sem ano: prefere a variante cujo ano mais recente seja o maior.
            best_year = -1
            for model in model_candidates[:30]:
                anos = await http.get_json(
                    f"{_BASE}/{tipo}/marcas/{brand['codigo']}/modelos/{model['codigo']}/anos"
                )
                try:
                    year = _pick_year(anos, None)
                except ValueError:
                    continue
                year_num = _year_of(year) or 0
                if year_num > best_year:
                    best_year = year_num
                    chosen = (model, year)
                if year_num >= datetime.now().year - 1:
                    break  # já achou algo bem recente
        else:
            for model in model_candidates:
                anos = await http.get_json(
                    f"{_BASE}/{tipo}/marcas/{brand['codigo']}/modelos/{model['codigo']}/anos"
                )
                try:
                    year = _pick_year(anos, ano)
                except ValueError:
                    continue  # variante sem o ano pedido: tenta a próxima
                chosen = (model, year)
                break

        if chosen is None:
            raise ValueError(
                f"Nada encontrado para {marca!r} {modelo!r}"
                + (f" no ano {ano}" if ano is not None else "")
                + "."
            )

        model, year = chosen
        detail = await http.get_json(
            f"{_BASE}/{tipo}/marcas/{brand['codigo']}/modelos/{model['codigo']}/anos/{year['codigo']}"
        )

    def add(kind: str, key: str, confidence: Confidence = Confidence.HIGH) -> None:
        value = detail.get(key)
        if value not in (None, ""):
            report.findings.append(
                Finding(source="fipe", kind=kind, value=str(value), confidence=confidence)
            )

    add("price", "Valor")
    add("brand", "Marca")
    add("model", "Modelo")
    add("year", "AnoModelo")
    add("fuel", "Combustivel")
    add("code", "CodigoFipe")
    add("reference", "MesReferencia")
    add("vehicle-type", "TipoVeiculo")

    return report


def _year_of(entry: dict) -> int | None:
    match = re.match(r"(\d{4})", str(entry.get("nome", "")))
    return int(match.group(1)) if match else None


def _pick_year(anos: list[dict], ano: int | None) -> dict:
    if not anos:
        raise ValueError("Nenhum ano disponível para esse modelo.")
    if ano is not None:
        wanted = str(ano)
        matches = [a for a in anos if str(a.get("nome", "")).startswith(wanted + " ")]
        if not matches:
            available = ", ".join(str(a.get("nome", "")) for a in anos[:10])
            raise ValueError(f"Ano {ano} não encontrado. Disponíveis: {available}")
        return matches[0]

    # Sem ano pedido: escolhe o mais recente plausível (ignora códigos anômalos).
    limit = datetime.now().year + 1
    dated = [(y, a) for a in anos if (y := _year_of(a)) and 1900 <= y <= limit]
    if dated:
        return max(dated, key=lambda pair: pair[0])[1]
    return anos[-1]