"""Providers embutidos e seu carregamento."""

from publiceye.providers import (  # noqa: F401
    cnpj,
    coingecko,
    crtsh,
    dns,
    geoip,
    open_meteo,
    rdap,
    viacep,
)


def load() -> None:
    """Garante que todos os providers embutidos estejam registrados."""
    return None
