"""Provider: CoinGecko (cotação e dados de criptomoeda).

API pública, sem chave para os endpoints usados. Resolve a moeda por id,
símbolo ou nome e devolve preço em USD/BRL, variação 24h e market cap.
Docs: https://docs.coingecko.com/
"""

from __future__ import annotations

import unicodedata
from datetime import datetime, timezone

from publiceye.core.models import Confidence, Finding, TargetType
from publiceye.core.provider import Provider, ProviderContext
from publiceye.core.registry import register
from publiceye.utils.http import HttpClient

_BASE = "https://api.coingecko.com/api/v3"


@register
class CoinGeckoProvider(Provider):
    name = "coingecko"
    description = "Cotação e dados de criptomoeda (CoinGecko, sem chave)."
    target_types = (TargetType.CRYPTO,)

    async def run(self, target: str, ctx: ProviderContext) -> list[Finding]:
        query = target.strip()
        if not query:
            return []

        async with HttpClient(ctx, min_interval=3.0) as http:
            search = await http.get_json(f"{_BASE}/search", params={"query": query})
            coin = _pick_coin(query, search.get("coins", []) or [])
            if coin is None:
                raise ValueError(f"Criptomoeda não encontrada: {query!r}")

            coin_id = coin["id"]
            prices = await http.get_json(
                f"{_BASE}/simple/price",
                params={
                    "ids": coin_id,
                    "vs_currencies": "usd,brl",
                    "include_24hr_change": "true",
                    "include_market_cap": "true",
                    "include_last_updated_at": "true",
                },
            )

        data = prices.get(coin_id) or {}
        findings: list[Finding] = []

        def add(kind: str, value: object, confidence: Confidence) -> None:
            if value not in (None, ""):
                findings.append(
                    Finding(
                        source=self.name,
                        kind=kind,
                        value=str(value),
                        confidence=confidence,
                    )
                )

        add("crypto:id", coin.get("id"), Confidence.HIGH)
        add("crypto:name", coin.get("name"), Confidence.HIGH)
        add("crypto:symbol", str(coin.get("symbol", "")).upper(), Confidence.HIGH)

        usd = data.get("usd")
        brl = data.get("brl")
        if usd is not None:
            add("crypto:price_usd", f"US$ {_fmt(usd)}", Confidence.HIGH)
        if brl is not None:
            add("crypto:price_brl", f"R$ {_fmt(brl)}", Confidence.HIGH)

        change = data.get("usd_24h_change")
        if change is not None:
            add("crypto:change_24h_usd", f"{change:+.2f}%", Confidence.HIGH)

        market_cap = data.get("usd_market_cap")
        if market_cap is not None:
            add("crypto:market_cap_usd", f"US$ {_fmt(market_cap)}", Confidence.MEDIUM)

        updated = data.get("last_updated_at")
        if updated:
            stamp = datetime.fromtimestamp(int(updated), tz=timezone.utc)
            add("crypto:last_updated", stamp.isoformat(), Confidence.HIGH)

        return findings


def _fmt(value: float) -> str:
    """Formata números grandes com separador e moedas pequenas com precisão."""
    if value >= 1:
        return f"{value:,.2f}"
    return f"{value:.8f}".rstrip("0").rstrip(".")


def _norm(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip().lower()


def _pick_coin(query: str, coins: list[dict]) -> dict | None:
    """Escolhe a moeda mais provável: id/símbolo exatos primeiro, depois nome."""
    q = _norm(query)
    if not q or not coins:
        return None

    def score(coin: dict) -> tuple[int, int]:
        coin_id = _norm(str(coin.get("id", "")))
        symbol = _norm(str(coin.get("symbol", "")))
        name = _norm(str(coin.get("name", "")))
        rank = coin.get("market_cap_rank") or 10**9
        if q in (coin_id, symbol):
            return (3, -rank)
        if name == q:
            return (2, -rank)
        if symbol.startswith(q) or name.startswith(q):
            return (1, -rank)
        return (0, -rank)

    best = max(coins, key=score)
    return best if score(best)[0] > 0 else None
