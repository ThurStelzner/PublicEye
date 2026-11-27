"""Integração com a API de Dados Abertos da Câmara dos Deputados.

Fonte pública e oficial (transparência), sem chave de API.
Docs: https://dadosabertos.camara.leg.br/

Política de privacidade do PublicEye: expomos apenas dados do *mandato*
(partido, UF, situação, gabinete, contato oficial, site/redes oficiais).
Campos pessoais presentes na API (CPF, nascimento, escolaridade) são
deliberadamente ignorados.
"""

from __future__ import annotations

from publiceye.core.models import Confidence, Finding, Report
from publiceye.core.provider import ProviderContext
from publiceye.utils.http import HttpClient

BASE = "https://dadosabertos.camara.leg.br/api/v2"


async def consultar_deputado(
    nome: str | None = None,
    *,
    deputado_id: int | None = None,
    uf: str | None = None,
    partido: str | None = None,
    fetch_all: bool = False,
    ctx: ProviderContext | None = None,
) -> Report:
    """Busca um deputado por nome (ou id) e devolve um Report com o mandato.

    Com ``fetch_all=True``, lista todos os deputados (paginando), sem detalhar.
    """
    if not fetch_all and not nome and deputado_id is None:
        raise ValueError("Informe um nome, --id ou use --all.")

    ctx = ctx or ProviderContext()
    report = Report(
        target=nome or (f"id {deputado_id}" if deputado_id else "todos os deputados"),
        target_type="politico",
    )

    async with HttpClient(ctx, min_interval=0.5) as http:
        if deputado_id is None:
            matches = await _search(http, nome or "", uf, partido, fetch_all=fetch_all)
            if not matches:
                raise ValueError(f"Nenhum deputado encontrado para {nome!r}.")
            if fetch_all or len(matches) > 1:
                for dep in matches:
                    report.findings.append(
                        Finding(
                            source="camara",
                            kind="match",
                            value=f"{dep['nome']} ({dep.get('siglaPartido', '?')}-{dep.get('siglaUf', '?')})",
                            confidence=Confidence.HIGH,
                            data={"id": dep.get("id")},
                        )
                    )
                return report
            deputado_id = matches[0]["id"]

        detail = await _detail(http, deputado_id)

    report.target = detail.get("ultimoStatus", {}).get("nome") or report.target
    report.findings.extend(_detail_findings(detail))
    return report


async def _search(
    http: HttpClient,
    nome: str,
    uf: str | None,
    partido: str | None,
    fetch_all: bool = False,
) -> list[dict]:
    params: dict = {
        "nome": nome,
        "itens": "1000" if fetch_all else "15",
        "ordem": "ASC",
        "ordenarPor": "nome",
    }
    if uf:
        params["siglaUf"] = uf.upper()
    if partido:
        params["siglaPartido"] = partido.upper()

    data = await http.get_json(f"{BASE}/deputados", params=params)
    if not isinstance(data, dict):
        return []

    results = list(data.get("dados", []))
    if not fetch_all:
        return results

    # Segue os links "next" até o fim (com trava de segurança).
    next_url = _next_link(data)
    pages = 1
    while next_url and pages < 20:
        data = await http.get_json(next_url)
        if not isinstance(data, dict):
            break
        results.extend(data.get("dados", []))
        next_url = _next_link(data)
        pages += 1
    return results


def _next_link(data: dict) -> str | None:
    for link in data.get("links", []) or []:
        if link.get("rel") == "next":
            return link.get("href")
    return None


async def _detail(http: HttpClient, deputado_id: int) -> dict:
    data = await http.get_json(f"{BASE}/deputados/{deputado_id}")
    return data.get("dados", {}) if isinstance(data, dict) else {}


def _detail_findings(detail: dict) -> list[Finding]:
    status = detail.get("ultimoStatus", {}) or {}
    gabinete = status.get("gabinete", {}) or {}
    findings: list[Finding] = []

    def add(kind: str, value, confidence: Confidence = Confidence.HIGH) -> None:
        if value not in (None, "", [], {}):
            findings.append(
                Finding(source="camara", kind=kind, value=str(value), confidence=confidence)
            )

    add("nome", status.get("nome") or detail.get("nomeCivil"))
    add("partido", status.get("siglaPartido"))
    add("uf", status.get("siglaUf"))
    add("situacao", status.get("situacao"))
    add("condicao", status.get("condicaoEleitoral"))
    add("legislatura", status.get("idLegislatura"))

    add("email", status.get("email") or gabinete.get("email"))
    add("telefone", gabinete.get("telefone"))
    sala = gabinete.get("sala")
    if sala:
        predio = gabinete.get("predio")
        add("gabinete", f"sala {sala}" + (f", prédio {predio}" if predio else ""))

    site = detail.get("urlWebsite")
    if isinstance(site, list):
        for url in site:
            add("website", url)
    elif site:
        add("website", site)

    for url in detail.get("redeSocial", []) or []:
        add("rede-social", url)

    return findings
