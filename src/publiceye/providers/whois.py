"""Provider: WHOIS (registro público de domínio/IP).

Consulta o protocolo WHOIS clássico (TCP porta 43), começando pelo bootstrap
da IANA (`whois.iana.org`) e seguindo as referências até o registro
autoritativo. O formato é texto livre, então o parser aceita rótulos
variados (`Domain Name`, `domain`, `titular`...) e descarta avisos/termos.
Documentação: https://www.iana.org/domains/root/db
"""

from __future__ import annotations

import asyncio
import re

from publiceye.core.models import Confidence, Finding, TargetType
from publiceye.core.provider import Provider, ProviderContext
from publiceye.core.registry import register

_IANA = "whois.iana.org"
_PORT = 43
_MAX_QUERIES = 2  # IANA + registro autoritativo (evita abuso de portas 43)
_DELAY = 1.0  # intervalo entre consultas, por educação com os servidores
_MAX_FINDINGS = 120

# Rótulos conhecidos -> tipo curto e estável no relatório.
_ALIASES = {
    "domain name": "domain",
    "domain": "domain",
    "registrar": "registrar",
    "creation date": "created",
    "created": "created",
    "created on": "created",
    "registered": "created",
    "registered on": "created",
    "registration time": "created",
    "data de criação": "created",
    "updated date": "updated",
    "last updated": "updated",
    "last updated on": "updated",
    "changed": "updated",
    "changed on": "updated",
    "last modified": "updated",
    "modified": "updated",
    "alterado": "updated",
    "registry expiry date": "expires",
    "registrar registration expiration date": "expires",
    "expiration date": "expires",
    "expiry date": "expires",
    "expires": "expires",
    "expires on": "expires",
    "expiração": "expires",
    "expira em": "expires",
    "name server": "nameserver",
    "nameserver": "nameserver",
    "nameservers": "nameserver",
    "nserver": "nameserver",
    "servidor dns": "nameserver",
    "domain status": "status",
    "status": "status",
    "situação": "status",
    "dnssec": "dnssec",
    "netname": "netname",
    "net range": "netrange",
    "cidr": "cidr",
    "orgname": "org",
    "organization": "org",
    "org-name": "org",
    "descr": "org",
    "owner": "registrant",
    "registrant": "registrant",
    "registrant name": "registrant",
    "registrant organization": "registrant",
    "titular": "registrant",
    "responsible": "registrant",
    "country": "country",
    "país": "country",
    "orgabuseemail": "abuse_email",
    "abuse-mailbox": "abuse_email",
    "registrar abuse contact email": "abuse_email",
}

# Chaves internas de roteamento/avisos que não são dados do registro.
_SKIP_KEYS = {
    "refer",
    "referralserver",
    "registrar whois server",
    "whois",
    "source",
    "comment",
    "remarks",
    "notice",
    "terms of use",
    "url of the icann whois inaccuracy complaint form",
}

_REDACTED = (
    "redacted",
    "not disclosed",
    "data protected",
    "gdpr",
    "statutory masking",
    "non-public",
    "não divulgado",
    "omitido",
)

_STOP_KEYS = {
    "for",
    "to",
    "or",
    "and",
    "the",
    "by",
    "of",
    "in",
    "if",
    "you",
    "we",
    "this",
    "these",
    "please",
}


@register
class WhoisProvider(Provider):
    name = "whois"
    description = "Registro público de domínio/IP via WHOIS (TCP porta 43)."
    target_types = (TargetType.DOMAIN, TargetType.IP)

    async def run(self, target: str, ctx: ProviderContext) -> list[Finding]:
        query = target.strip().lower().rstrip(".")
        if not query:
            return []

        text = await _lookup(query, ctx.timeout)
        return _parse(text, self.name)


async def _lookup(query: str, timeout: float) -> str:
    """Consulta a IANA e segue a referência até o registro autoritativo."""
    timeout = min(timeout, 20.0)
    text = await _query(_IANA, query, timeout)
    host = _referral(text)
    if not host:
        return ""

    last_good = ""
    for attempt in range(1, _MAX_QUERIES):
        await asyncio.sleep(_DELAY)
        try:
            text = await _query(host, query, timeout)
        except (OSError, asyncio.TimeoutError):
            if not last_good:
                raise
            break
        if not text.strip():
            break
        last_good = text
        next_host = _referral(text)
        if not next_host or next_host == host:
            break
        host = next_host

    return last_good


async def _query(host: str, query: str, timeout: float) -> str:
    """Uma consulta WHOIS bruta: conecta, envia o termo e lê até EOF."""
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, _PORT), timeout=timeout
    )
    try:
        writer.write(f"{query}\r\n".encode("utf-8"))
        await writer.drain()
        chunks: list[bytes] = []
        while True:
            chunk = await asyncio.wait_for(reader.read(65536), timeout=timeout)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:  # conexão já encerrada pelo servidor
            pass
    return b"".join(chunks).decode("utf-8", "replace")


def _referral(text: str) -> str | None:
    """Extrai o próximo servidor WHOIS de linhas `refer:`, `whois:` etc."""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("%", "#", ">>>")):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            continue
        if key.strip().lower() not in {"refer", "whois", "registrar whois server", "referralserver"}:
            continue
        host = value.strip()
        if host.lower().startswith("whois://"):
            host = host[len("whois://"):]
        host = host.strip("/")
        host = host.split()[0] if host.split() else ""
        host = host.split("/")[0].split(":")[0]
        if host and "." in host:
            return host.lower()
    return None


def _parse(text: str, source: str) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[tuple[str, str]] = set()

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("%", "#", ">>>")):
            continue

        key, sep, value = line.partition(":")
        if not sep:
            continue
        key = " ".join(key.split()).lower()
        value = value.strip()
        if not key or not value or not _valid_key(key) or key in _SKIP_KEYS:
            continue
        value = _clean_value(key, value)
        if value is None:
            continue

        kind = f"whois:{_ALIASES.get(key, _slug(key))}"
        if (kind, value) in seen:
            continue
        seen.add((kind, value))
        findings.append(
            Finding(
                source=source,
                kind=kind,
                value=value,
                confidence=_confidence(key),
            )
        )
        if len(findings) >= _MAX_FINDINGS:
            break

    return findings


def _valid_key(key: str) -> bool:
    """Distingue rótulo (`Domain Name`) de prosa que contém `:`, como URLs."""
    if len(key) > 40 or "," in key or "?" in key or "http" in key or "www" in key:
        return False
    words = key.split()
    if len(words) > 5 or words[0] in _STOP_KEYS:
        return False
    return True


def _clean_value(key: str, value: str) -> str | None:
    if len(value) > 300:
        return None
    folded = value.casefold()
    if any(folded.startswith(token) for token in _REDACTED):
        return None

    if key in {"name server", "nameserver", "nameservers", "nserver", "servidor dns"}:
        return value.split()[0].rstrip(".").lower() or None

    if key in {"domain status", "status", "situação"}:
        value = value.split(" http")[0].strip()

    return value or None


def _confidence(key: str) -> Confidence:
    if key in {"owner", "registrant", "registrant name", "registrant organization", "titular", "responsible", "orgabuseemail", "abuse-mailbox", "registrar abuse contact email"}:
        return Confidence.MEDIUM
    return Confidence.HIGH


def _slug(key: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")
    return slug or "field"
