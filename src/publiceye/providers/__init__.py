"""Providers embutidos e seu carregamento."""

from publiceye.providers import crtsh, rdap  # noqa: F401


def load() -> None:
    """Garante que todos os providers embutidos estejam registrados."""
    return None
