"""Cache em disco das respostas HTTP dos providers.

Guarda o corpo já decodificado de cada requisição GET, com TTL, num diretório
de cache. A chave é um hash de método + URL + parâmetros, então requisições
idênticas reaproveitam a resposta dentro da janela de validade.

Configuração por variáveis de ambiente (lidas em `ProviderContext`):
- ``PUBLICEEYE_CACHE_DIR``  diretório do cache
- ``PUBLICEEYE_CACHE_TTL``  validade padrão em segundos
- ``PUBLICEEYE_NO_CACHE``   ``1``/``true`` desliga o cache
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

DEFAULT_TTL = 3600.0


def default_cache_dir() -> Path:
    """Diretório padrão do cache, respeitando o SO e a env de override."""
    override = os.environ.get("PUBLICEEYE_CACHE_DIR")
    if override:
        return Path(override)
    local = os.environ.get("LOCALAPPDATA")
    root = Path(local) if local else Path.home() / ".cache"
    return root / "publiceye" / "cache"


def _normalize_params(params: Any) -> Any:
    """Normaliza `params` do httpx para uma forma estável e serializável."""
    if params is None:
        return None
    if isinstance(params, dict):
        return {str(k): params[k] for k in sorted(params, key=str)}
    try:
        return sorted([str(k), str(v)] for k, v in params)
    except (TypeError, ValueError):
        return str(params)


class ResponseCache:
    """Cache simples em disco: uma entrada JSON por requisição."""

    def __init__(
        self, directory: str | Path | None = None, default_ttl: float = DEFAULT_TTL
    ) -> None:
        self.directory = Path(directory) if directory else default_cache_dir()
        self.default_ttl = default_ttl
        self.hits = 0
        self.misses = 0

    @staticmethod
    def _key(method: str, url: str, params: Any) -> str:
        raw = json.dumps(
            {"m": method.upper(), "u": url, "p": _normalize_params(params)},
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _path(self, key: str) -> Path:
        # Dois níveis de subpasta evitam diretórios gigantes num só lugar.
        return self.directory / key[:2] / f"{key}.json"

    def get(self, method: str, url: str, params: Any, ttl: float) -> Any | None:
        """Devolve o valor cacheado se ainda for válido, senão ``None``."""
        if ttl <= 0:
            return None
        path = self._path(self._key(method, url, params))
        try:
            entry = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            self.misses += 1
            return None
        stored_at = entry.get("stored_at", 0)
        if time.time() - stored_at > ttl:
            self.misses += 1
            return None
        self.hits += 1
        return entry.get("value")

    def set(
        self, method: str, url: str, params: Any, value: Any, ttl: float
    ) -> None:
        """Grava o valor; chamadas com ``ttl <= 0`` não são cacheadas."""
        if ttl <= 0:
            return
        path = self._path(self._key(method, url, params))
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "method": method.upper(),
            "url": url,
            "stored_at": time.time(),
            "ttl": ttl,
            "value": value,
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(entry, ensure_ascii=False, default=str), "utf-8"
        )
        os.replace(tmp, path)

    def stats(self) -> tuple[int, int]:
        """Devolve (quantidade de entradas, bytes ocupados) no disco."""
        if not self.directory.exists():
            return (0, 0)
        count = 0
        total = 0
        for path in self.directory.rglob("*.json"):
            try:
                total += path.stat().st_size
                count += 1
            except OSError:
                continue
        return (count, total)

    def clear(self) -> int:
        """Apaga todo o cache e devolve quantas entradas foram removidas."""
        count, _ = self.stats()
        if self.directory.exists():
            shutil.rmtree(self.directory, ignore_errors=True)
        return count


_DEFAULT_CACHE: ResponseCache | None = None


def get_default_cache() -> ResponseCache:
    """Instância compartilhada do cache padrão (agrega estatísticas do run)."""
    global _DEFAULT_CACHE
    if _DEFAULT_CACHE is None:
        _DEFAULT_CACHE = ResponseCache()
    return _DEFAULT_CACHE
