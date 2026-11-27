"""Utilidades de rede: cliente HTTP assíncrono, educado e identificado."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from publiceye.core.provider import ProviderContext

# Status tratados como transitórios (vale retentar).
RETRY_STATUSES = {429, 500, 502, 503, 504}


class RateLimiter:
    """Limite simples de requisições por segundo, por host."""

    def __init__(self, min_interval: float) -> None:
        self._min_interval = min_interval
        self._lock = asyncio.Lock()
        self._last: float = 0.0

    async def wait(self) -> None:
        async with self._lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            delta = now - self._last
            if delta < self._min_interval:
                await asyncio.sleep(self._min_interval - delta)
                now = loop.time()
            self._last = now


class HttpClient:
    """Wrapper sobre httpx.AsyncClient que se identifica, respeita limites e retenta."""

    def __init__(self, ctx: ProviderContext, min_interval: float = 0.5) -> None:
        self._ctx = ctx
        self._limiter = RateLimiter(min_interval)
        self._client = httpx.AsyncClient(
            timeout=ctx.timeout,
            headers={
                "User-Agent": ctx.user_agent,
                "Accept": "application/json, text/plain, */*",
            },
            follow_redirects=True,
        )

    async def __aenter__(self) -> "HttpClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self._client.aclose()

    async def get_json(
        self,
        url: str,
        *,
        retries: int = 2,
        retry_statuses: set[int] | None = None,
        **kwargs: Any,
    ) -> Any:
        statuses = retry_statuses if retry_statuses is not None else RETRY_STATUSES
        resp = await self._get(url, retries=retries, retry_statuses=statuses, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def get_text(
        self, url: str, *, retries: int = 2, **kwargs: Any
    ) -> str:
        resp = await self._get(url, retries=retries, **kwargs)
        resp.raise_for_status()
        return resp.text

    async def _get(
        self,
        url: str,
        *,
        retries: int = 2,
        retry_statuses: set[int] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        statuses = retry_statuses if retry_statuses is not None else RETRY_STATUSES
        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            await self._limiter.wait()
            try:
                resp = await self._client.get(url, **kwargs)
                if resp.status_code in statuses and attempt < retries:
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                return resp
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt < retries:
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                raise
        assert last_exc is not None
        raise last_exc

