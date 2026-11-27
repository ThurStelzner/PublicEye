"""Registry de providers — plugins se registram com um decorator."""

from __future__ import annotations

from publiceye.core.models import TargetType
from publiceye.core.provider import Provider

_REGISTRY: dict[str, type[Provider]] = {}


def register(cls: type[Provider]) -> type[Provider]:
    """Decorator que registra uma classe de Provider pelo seu `name`."""
    key = cls.name.lower()
    if key in _REGISTRY:
        raise ValueError(f"Provider duplicado: {cls.name!r}")
    _REGISTRY[key] = cls
    return cls


def all_providers() -> dict[str, type[Provider]]:
    return dict(_REGISTRY)


def get(name: str) -> type[Provider]:
    try:
        return _REGISTRY[name.lower()]
    except KeyError as exc:
        known = ", ".join(sorted(_REGISTRY)) or "<nenhum>"
        raise KeyError(f"Provider {name!r} não existe. Conhecidos: {known}") from exc


def providers_for(target_type: TargetType) -> list[type[Provider]]:
    return [
        cls
        for cls in _REGISTRY.values()
        if not cls.target_types or target_type in cls.target_types
    ]


def load_builtin() -> None:
    """Importa os providers embutidos para popular o registry."""
    from publiceye.providers import load  # noqa: F401  (efeito colateral)
