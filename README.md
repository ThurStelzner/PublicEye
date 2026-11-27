# PublicEye

> OSINT **family friendly**: aberto, ético e 100% legal. Só fontes públicas e APIs legítimas — nada de invasão, scraping abusivo ou dado vazado.

PublicEye é uma ferramenta de **OSINT (Open-Source Intelligence)** construída para investigar e correlacionar informação **publicamente disponível** — de forma transparente, reproduzível e dentro da lei. Não é focada em família nem em monitoramento de pessoas: o "family friendly" aqui significa **uso responsável**, sem features obscuras ou invasivas.

## Princípios

- **Legalidade total.** Cada fonte é pública ou uma API oficial. Se não é legal consultar, não entra no projeto.
- **Sem credenciais roubadas, sem vazamentos, sem bypass.** Nada de dados de breaches, senhas, tokens ou CAPTCHA/anti-bot burlado.
- **Transparência.** Toda coleta passa por APIs documentadas e registráveis.
- **Privacidade por padrão.** Respeita `robots.txt`, limites de taxa e termos de uso das fontes.
- **Reprodutibilidade.** Toda consulta pode ser auditada e refeita.

## O que é / o que NÃO é

| ✅ É | ❌ Não é |
| --- | --- |
| Consulta a APIs públicas e registradas | Uso de dados vazados (`combo lists`, breaches) |
| Enriquecimento de dados abertos | Doxxing ou perseguição |
| Correlação de fontes oficiais | Acesso não autorizado a sistemas |
| Automação ética e com rate limit | Bypass de autenticação, paywall ou CAPTCHA |
| Ferramenta educacional e de pesquisa | Vigilância de pessoas sem consentimento |

## Fontes

Todas públicas e com API/ToS que permitem uso.

**Implementadas**

- Domínios e DNS: RDAP, WHOIS, DNS over HTTPS (DoH) e Certificate Transparency (crt.sh)
- GeoIP / ASN de IPs (ipwho.is)
- Geocodificação direta e reversa (Nominatim / OSM)
- Endereços e CEPs (ViaCEP)
- Dados públicos de empresas por CNPJ (BrasilAPI / Receita Federal)
- Tabela FIPE (preço de veículos)
- Clima (Open-Meteo)
- Cotações de criptomoedas (CoinGecko)
- Dados do mandato de deputados federais (Câmara dos Deputados)

**Planejadas**

- Dados abertos governamentais (Brasil e internacionais)
- APIs de notícias e conteúdo aberto

> Nenhuma fonte entra sem revisão de termos de uso e licença.

## Uso

Requer Python 3.10+. Com [uv](https://docs.astral.sh/uv/):

```bash
uv venv .venv
uv pip install -e ".[dev]"
```

Depois:

```bash
publiceye providers                    # lista as fontes disponíveis
publiceye scan example.com             # coleta em domínio (usa todos os providers)
publiceye scan example.com -p rdap     # só um provider
publiceye scan example.com -p dns      # registros DNS via DoH
publiceye scan example.com -p whois    # registro WHOIS (porta 43)
publiceye scan 8.8.8.8                 # IP (inclui DNS reverso/PTR)
publiceye cep 01310-100                # endereço de um CEP (ViaCEP)
publiceye cnpj 11.222.333/0001-81      # dados públicos de uma empresa (CNPJ)
publiceye weather -23.55,-46.63        # clima atual por coordenadas (Open-Meteo)
publiceye weather "São Paulo"          # clima atual por cidade (Open-Meteo)
publiceye coin bitcoin                 # cotação de criptomoeda (CoinGecko)
publiceye geocode "Avenida Paulista, São Paulo"   # endereço → coordenadas
publiceye geocode -23.55,-46.63 --reverse         # coordenadas → endereço
publiceye fipe Fiat Uno --ano 2019     # preço de veículo na Tabela FIPE
publiceye camara "Arthur Lira"         # dados do mandato de um deputado
publiceye scan exemplo.com --json      # saída JSON
publiceye scan exemplo.com -o out.json # salva o relatório
```

Exemplo de saída:

```
Alvo: example.com (domain) — 36 achados
Fonte  | Tipo            | Valor                       | Confiança
rdap   | event:created   | 1995-08-14T04:00:00Z        | high
rdap   | nameserver      | hera.ns.cloudflare.com      | high
whois  | whois:registrar | RESERVED-Internet Assigned… | high
dns    | dns:mx          | 10 mail.example.com         | high
crtsh  | subdomain       | www.example.com             | high
...
```

### Arquitetura

- `core/` — modelos, contrato de `Provider`, registry e orquestração
- `providers/` — uma fonte pública por arquivo (RDAP, WHOIS, DNS/DoH, Certificate Transparency, GeoIP…)
- `utils/` — cliente HTTP educado (rate limit, retry, User-Agent próprio)
- `cli.py` — interface de linha de comando (Typer + Rich)

### Criando um novo provider

Basta um arquivo em `src/publiceye/providers/` e registrar com o decorator:

```python
from publiceye.core.models import Finding, TargetType
from publiceye.core.provider import Provider, ProviderContext
from publiceye.core.registry import register

@register
class MinhaFonte(Provider):
    name = "minha-fonte"
    description = "descrição curta da fonte pública"
    target_types = (TargetType.DOMAIN,)

    async def run(self, target: str, ctx: ProviderContext) -> list[Finding]:
        ...
```

## Uso ético

Use o PublicEye apenas para:

- Pesquisa acadêmica e jornalismo de interesse público
- Segurança defensiva e verificação de superfície de exposição **da própria organização**
- Educação em OSINT

Não use para assediar, constranger ou coletar dados pessoais de terceiros sem base legal.

## Roadmap

- [x] Estrutura inicial do projeto
- [x] Módulo de coleta com providers plugáveis (RDAP, Certificate Transparency)
- [x] Rate limiting e retry por provider
- [x] CLI com saída em tabela e JSON
- [x] Mais fontes de dados abertos e GeoIP (ViaCEP, CNPJ, FIPE, Câmara, Open-Meteo, CoinGecko, ipwho.is)
- [x] DNS público via DNS over HTTPS (DoH)
- [ ] Cache de respostas por provider
- [x] WHOIS (TCP porta 43) para domínios e IPs
- [x] Geocodificação direta e reversa (Nominatim / OSM)
- [ ] Frontend de grafo (estilo Maltego)
- [ ] Testes e documentação de cada fonte

## Licença

MIT — veja [LICENSE](LICENSE).
