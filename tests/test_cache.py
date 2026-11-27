import httpx
import pytest

from publiceye.core.provider import ProviderContext
from publiceye.utils import cache as cache_mod
from publiceye.utils.cache import ResponseCache
from publiceye.utils.http import HttpClient


def test_cache_roundtrip(tmp_path):
    cache = ResponseCache(tmp_path)
    cache.set("GET", "https://x/api", {"a": 1}, {"ok": True}, ttl=60)
    assert cache.get("GET", "https://x/api", {"a": 1}, ttl=60) == {"ok": True}
    assert cache.hits == 1


def test_cache_key_is_param_order_independent(tmp_path):
    cache = ResponseCache(tmp_path)
    cache.set("GET", "https://x/api", {"a": 1, "b": 2}, "v", ttl=60)
    assert cache.get("GET", "https://x/api", {"b": 2, "a": 1}, ttl=60) == "v"


def test_cache_expires(tmp_path, monkeypatch):
    now = {"t": 1000.0}
    monkeypatch.setattr(cache_mod.time, "time", lambda: now["t"])
    cache = ResponseCache(tmp_path)
    cache.set("GET", "https://x/api", None, "v", ttl=60)
    now["t"] = 1030.0
    assert cache.get("GET", "https://x/api", None, ttl=60) == "v"
    now["t"] = 1200.0
    assert cache.get("GET", "https://x/api", None, ttl=60) is None


def test_cache_disabled_when_ttl_zero(tmp_path):
    cache = ResponseCache(tmp_path)
    cache.set("GET", "https://x/api", None, "v", ttl=0)
    assert cache.get("GET", "https://x/api", None, ttl=0) is None
    assert cache.stats() == (0, 0)


def test_cache_clear(tmp_path):
    cache = ResponseCache(tmp_path)
    cache.set("GET", "https://x/a", None, "1", ttl=60)
    cache.set("GET", "https://x/b", None, "2", ttl=60)
    assert cache.stats()[0] == 2
    assert cache.clear() == 2
    assert cache.stats() == (0, 0)


async def test_httpclient_uses_cache(tmp_path):
    ctx = ProviderContext(cache_dir=str(tmp_path), cache_ttl=60.0)
    client = HttpClient(ctx)
    calls = {"n": 0}

    async def fake_get(url, **kwargs):
        calls["n"] += 1
        return httpx.Response(200, json={"v": 1}, request=httpx.Request("GET", url))

    client._get = fake_get  # type: ignore[assignment]
    try:
        first = await client.get_json("https://x/api", params={"a": 1})
        second = await client.get_json("https://x/api", params={"a": 1})
    finally:
        await client._client.aclose()

    assert first == second == {"v": 1}
    assert calls["n"] == 1


async def test_httpclient_no_cache_when_disabled(tmp_path):
    ctx = ProviderContext(cache_dir=str(tmp_path), use_cache=False)
    client = HttpClient(ctx)
    calls = {"n": 0}

    async def fake_get(url, **kwargs):
        calls["n"] += 1
        return httpx.Response(200, json={"v": 1}, request=httpx.Request("GET", url))

    client._get = fake_get  # type: ignore[assignment]
    try:
        await client.get_json("https://x/api")
        await client.get_json("https://x/api")
    finally:
        await client._client.aclose()

    assert calls["n"] == 2
    assert client._cache is None
