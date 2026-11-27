"""Providers embutidos e seu carregamento."""

from publiceye.providers import crtsh, geoip, rdap, viacep  # noqa: F401


def load() -> None:
    """Garante que todos os providers embutidos estejam registrados."""
    return None
