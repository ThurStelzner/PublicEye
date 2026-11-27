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
from publiceye.core.fipe import search_fipe
from publiceye.core.models import TargetType
from publiceye.core.provider import detect_target_type
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
    target: str = typer.Argument(..., help="Domínio, IP, e-mail, CEP ou CNPJ a investigar."),
    provider: Optional[list[str]] = typer.Option(
        None, "--provider", "-p", help="Executar só estes providers (repetível)."
    ),
    target_type: Optional[str] = typer.Option(
        None, "--type", help="Força o tipo do alvo: domain | ip | email | cep | cnpj."
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
