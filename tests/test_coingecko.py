import pytest

from publiceye.core.models import TargetType
from publiceye.core.provider import ProviderContext
from publiceye.providers import coingecko as cg_mod

SEARCH = {
    "coins": [
        {"id": "bitcoin", "name": "Bitcoin", "symbol": "btc", "market_cap_rank": 1},
        {
            "id": "bitcoin-cash",
            "name": "Bitcoin Cash",
            "symbol": "bch",
            "market_cap_rank": 20,
        },
    ]
}

PRICES = {
    "bitcoin": {
        "usd": 67000.5,
        "brl": 350000.0,
        "usd_24h_change": -1.234,
        "usd_market_cap": 1_300_000_000_000,
        "last_updated_at": 1_750_000_000,
    }
}


class _FakeHttp:
    def __init__(self, search, prices):
        self._search = search
        self._prices = prices

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def get_json(self, url, **kwargs):
        if url.endswith("/search"):
            return self._search
        return self._prices


@pytest.fixture
def patch_http(monkeypatch):
    def _apply(search=SEARCH, prices=PRICES):
        monkeypatch.setattr(
            cg_mod,
            "HttpClient",
            lambda ctx, min_interval=3.0: _FakeHttp(search, prices),
        )

    return _apply


async def test_coin_parses_prices(patch_http):
    patch_http()
    findings = await cg_mod.CoinGeckoProvider().run("btc", ProviderContext())
    kinds = {f.kind: f.value for f in findings}
    assert kinds["crypto:id"] == "bitcoin"
    assert kinds["crypto:symbol"] == "BTC"
    assert kinds["crypto:price_usd"] == "US$ 67,000.50"
    assert kinds["crypto:price_brl"] == "R$ 350,000.00"
    assert kinds["crypto:change_24h_usd"] == "-1.23%"
    assert kinds["crypto:market_cap_usd"] == "US$ 1,300,000,000,000.00"


async def test_coin_unknown_raises(patch_http):
    patch_http(search={"coins": []})
    with pytest.raises(ValueError):
        await cg_mod.CoinGeckoProvider().run("naoexiste", ProviderContext())


def test_pick_coin_prefers_exact_symbol():
    coin = cg_mod._pick_coin("bch", SEARCH["coins"])
    assert coin["id"] == "bitcoin-cash"


def test_coin_only_supports_crypto():
    assert cg_mod.CoinGeckoProvider.supports(TargetType.CRYPTO)
    assert not cg_mod.CoinGeckoProvider.supports(TargetType.DOMAIN)
