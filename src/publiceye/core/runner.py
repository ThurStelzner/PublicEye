"""Orquestra a execução dos providers sobre um alvo."""

from __future__ import annotations

import asyncio

from publiceye.core.models import (
    ProviderError,
    Report,
    TargetType,
)
from publiceye.core.provider import ProviderContext, detect_target_type
from publiceye.core.registry import get, providers_for


async def run_scan(
    target: str,
    *,
    providers: list[str] | None = None,
    target_type: TargetType | None = None,
    ctx: ProviderContext | None = None,
) -> Report:
    """Executa os providers aplicáveis e agrega achados e erros.

    Um provider que falha não derruba os outros: o erro é registrado no
    relatório e a coleta continua.
    """
    ctx = ctx or ProviderContext()
    target = target.strip()
    ttype = target_type or detect_target_type(target)

    if providers:
        selected = [get(name) for name in providers]
    else:
        selected = providers_for(ttype)

    applicable = [cls for cls in selected if cls.supports(ttype)]

    report = Report(target=target, target_type=ttype.value)

    async def _run_one(cls) -> tuple[list, ProviderError | None]:
        instance = cls()
        try:
            findings = await instance.run(target, ctx)
            return findings, None
        except Exception as exc:  # noqa: BLE001  — isola falha por provider
            message = str(exc) or type(exc).__name__
            return [], ProviderError(source=instance.name, error=message)

    results = await asyncio.gather(*(_run_one(cls) for cls in applicable))

    for findings, error in results:
        report.findings.extend(findings)
        if error:
            report.errors.append(error)

    report.findings.sort(key=lambda f: (f.source, f.kind, f.value))
    return report
