"""Interface de linha de comando do PublicEye."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from publiceye import __version__
from publiceye.core.camara import consultar_deputado
from publiceye.core.fipe import search_fipe
from publiceye.core.models import TargetType
from publiceye.core.provider import detect_target_type, parse_coordinates
from publiceye.core.registry import all_providers, load_builtin
from publiceye.core.runner import run_scan

app = typer.Typer(
    name="publiceye",
    help="OSINT family friendly: coleta ética a partir de fontes públicas.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _ensure_providers() -> None:
    load_builtin()


@app.command()
def version() -> None:
    """Mostra a versão do PublicEye."""
    console.print(f"publiceye [bold cyan]{__version__}[/bold cyan]")


@app.command("providers")
def list_providers() -> None:
    """Lista as fontes (providers) disponíveis."""
    _ensure_providers()
    table = Table(title="Providers")
    table.add_column("Nome", style="bold cyan")
    table.add_column("Alvos")
    table.add_column("Descrição")
    for cls in sorted(all_providers().values(), key=lambda c: c.name):
        alvos = ", ".join(t.value for t in cls.target_types) or "qualquer"
        table.add_row(cls.name, alvos, cls.description)
    console.print(table)


@app.command()
def scan(
    target: str = typer.Argument(
        ...,
        help="Domínio, IP, e-mail, CEP, CNPJ, coordenadas (lat,lon) ou local.",
    ),
    provider: Optional[list[str]] = typer.Option(
        None, "--provider", "-p", help="Executar só estes providers (repetível)."
    ),
    target_type: Optional[str] = typer.Option(
        None,
        "--type",
        help=(
            "Força o tipo do alvo: domain | ip | email | cep | cnpj | "
            "weather | crypto | place."
        ),
    ),
    as_json: bool = typer.Option(False, "--json", help="Saída em JSON."),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Salvar o relatório JSON neste arquivo."
    ),
) -> None:
    """Executa a coleta sobre um alvo e mostra os achados."""
    _ensure_providers()

    ttype = None
    if target_type:
        try:
            ttype = TargetType(target_type.lower())
        except ValueError:
            console.print(f"[red]Tipo inválido:[/red] {target_type}")
            raise typer.Exit(code=2) from None
    elif detect_target_type(target) is TargetType.UNKNOWN:
        console.print(
            f"[red]Não reconheci o alvo[/red] {target!r}. Use --type para forçar."
        )
        raise typer.Exit(code=2)

    report = asyncio.run(
        run_scan(target, providers=provider, target_type=ttype)
    )
    _emit(report, as_json, output)


@app.command()
def cep(
    value: str = typer.Argument(..., metavar="CEP", help="CEP, ex.: 01310-100 ou 01310100."),
    as_json: bool = typer.Option(False, "--json", help="Saída em JSON."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Salvar JSON."),
) -> None:
    """Consulta um CEP (endereço completo via ViaCEP)."""
    _ensure_providers()
    if detect_target_type(value) is not TargetType.CEP:
        console.print(f"[red]CEP inválido:[/red] {value!r}")
        raise typer.Exit(code=2)
    report = asyncio.run(
        run_scan(value, providers=["viacep"], target_type=TargetType.CEP)
    )
    _emit(report, as_json, output)


@app.command()
def cnpj(
    value: str = typer.Argument(
        ..., metavar="CNPJ", help="CNPJ, ex.: 11.222.333/0001-81 ou 11222333000181."
    ),
    as_json: bool = typer.Option(False, "--json", help="Saída em JSON."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Salvar JSON."),
) -> None:
    """Consulta um CNPJ (dados públicos da empresa via BrasilAPI)."""
    _ensure_providers()
    if detect_target_type(value) is not TargetType.CNPJ:
        console.print(f"[red]CNPJ inválido:[/red] {value!r}")
        raise typer.Exit(code=2)
    report = asyncio.run(
        run_scan(value, providers=["cnpj"], target_type=TargetType.CNPJ)
    )
    _emit(report, as_json, output)


@app.command(context_settings={"ignore_unknown_options": True})
def weather(
    value: str = typer.Argument(
        ...,
        metavar="LOCAL",
        help="Coordenadas (ex.: -23.55,-46.63) ou nome da cidade (ex.: São Paulo).",
    ),
    as_json: bool = typer.Option(False, "--json", help="Saída em JSON."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Salvar JSON."),
) -> None:
    """Clima atual por coordenadas ou cidade (Open-Meteo)."""
    _ensure_providers()
    report = asyncio.run(
        run_scan(value, providers=["open-meteo"], target_type=TargetType.WEATHER)
    )
    _emit(report, as_json, output)


@app.command()
def coin(
    value: str = typer.Argument(
        ..., metavar="MOEDA", help="ID, símbolo ou nome, ex.: bitcoin, btc, ethereum."
    ),
    as_json: bool = typer.Option(False, "--json", help="Saída em JSON."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Salvar JSON."),
) -> None:
    """Cotação e dados de uma criptomoeda (CoinGecko)."""
    _ensure_providers()
    report = asyncio.run(
        run_scan(value, providers=["coingecko"], target_type=TargetType.CRYPTO)
    )
    _emit(report, as_json, output)


@app.command(context_settings={"ignore_unknown_options": True})
def geocode(
    value: str = typer.Argument(
        ...,
        metavar="LOCAL",
        help="Endereço/local (ex.: 'Avenida Paulista, São Paulo') ou lat,lon com --reverse.",
    ),
    reverse: bool = typer.Option(
        False,
        "--reverse",
        "-r",
        help="Geocodificação reversa: trata o alvo como coordenadas (lat,lon).",
    ),
    as_json: bool = typer.Option(False, "--json", help="Saída em JSON."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Salvar JSON."),
) -> None:
    """Geocodificação direta (endereço → coordenadas) e reversa (Nominatim)."""
    _ensure_providers()
    if reverse and parse_coordinates(value) is None:
        console.print(f"[red]Coordenadas inválidas:[/red] {value!r}")
        raise typer.Exit(code=2)
    report = asyncio.run(
        run_scan(value, providers=["nominatim"], target_type=TargetType.PLACE)
    )
    _emit(report, as_json, output)


@app.command()
def fipe(
    marca: str = typer.Argument(..., help="Marca do veículo, ex.: Fiat."),
    modelo: str = typer.Argument(..., help="Modelo, ex.: Uno."),
    ano: Optional[int] = typer.Option(None, "--ano", "-a", help="Ano-modelo, ex.: 2019."),
    tipo: str = typer.Option("carros", "--tipo", help="carros | motos | caminhoes."),
    as_json: bool = typer.Option(False, "--json", help="Saída em JSON."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Salvar JSON."),
) -> None:
    """Preço e dados de um veículo na Tabela FIPE (marca/modelo/ano)."""
    try:
        report = asyncio.run(search_fipe(marca, modelo, ano=ano, tipo=tipo))
    except ValueError as exc:
        console.print(f"[red]Erro:[/red] {exc}")
        raise typer.Exit(code=2) from None
    _emit(report, as_json, output)


@app.command()
def camara(
    nome: Optional[str] = typer.Argument(None, help="Nome do deputado para buscar."),
    deputado_id: Optional[int] = typer.Option(None, "--id", help="ID do deputado na API."),
    uf: Optional[str] = typer.Option(None, "--uf", help="Filtrar por UF, ex.: SP."),
    partido: Optional[str] = typer.Option(None, "--partido", help="Filtrar por partido, ex.: PT."),
    fetch_all: bool = typer.Option(
        False, "--all", help="Lista todos os deputados (paginando), em vez de um só."
    ),
    as_json: bool = typer.Option(False, "--json", help="Saída em JSON."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Salvar JSON."),
) -> None:
    """Dados públicos do mandato de um deputado federal (Câmara dos Deputados)."""
    try:
        report = asyncio.run(
            consultar_deputado(
                nome, deputado_id=deputado_id, uf=uf, partido=partido, fetch_all=fetch_all
            )
        )
    except ValueError as exc:
        console.print(f"[red]Erro:[/red] {exc}")
        raise typer.Exit(code=2) from None
    _emit(report, as_json, output)


def _emit(report, as_json: bool, output: Optional[Path]) -> None:
    data = report.to_dict()
    if output:
        output.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
        console.print(f"[green]Relatório salvo em[/green] {output}")
    if as_json:
        console.print_json(json.dumps(data))
        return
    _print_report(data)


def _print_report(data: dict) -> None:
    console.print(
        f"\n[bold]Alvo:[/bold] {data['target']} "
        f"([cyan]{data['target_type']}[/cyan]) — "
        f"[bold]{data['count']}[/bold] achados"
    )
    if not data["findings"] and not data["errors"]:
        console.print("[yellow]Nenhum resultado. Fonte pode estar vazia ou indisponível.[/yellow]")
        return

    table = Table(show_lines=False)
    table.add_column("Fonte", style="cyan")
    table.add_column("Tipo", style="magenta")
    table.add_column("Valor")
    table.add_column("Confiança", justify="center")
    for f in data["findings"]:
        table.add_row(f["source"], f["kind"], str(f["value"]), f["confidence"])
    console.print(table)

    for err in data["errors"]:
        console.print(f"[red]erro[/red] ({err['source']}): {err['error']}")


if __name__ == "__main__":
    app()
