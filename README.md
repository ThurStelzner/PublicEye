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

## Fontes planejadas

Todas públicas e com API/ToS que permitem uso:

- Dados abertos governamentais (Brasil e internacionais)
- APIs de domínio e DNS (WHOIS, RDAP)
- Certificados públicos (Certificate Transparency / crt.sh)
- Geocodificação e mapas abertos (Nominatim / OSM)
- Registros públicos de empresas e diários oficiais
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
publiceye scan 8.8.8.8                 # IP
publiceye scan exemplo.com --json      # saída JSON
publiceye scan exemplo.com -o out.json # salva o relatório
```

Exemplo de saída:

```
Alvo: example.com (domain) — 36 achados
Fonte  | Tipo            | Valor                       | Confiança
rdap   | event:created   | 1995-08-14T04:00:00Z        | high
rdap   | nameserver      | hera.ns.cloudflare.com      | high
crtsh  | subdomain       | www.example.com             | high
...
```

### Arquitetura

- `core/` — modelos, contrato de `Provider`, registry e orquestração
- `providers/` — uma fonte pública por arquivo (RDAP, Certificate Transparency, GeoIP…)
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
- [ ] Cache de respostas por provider
- [ ] Mais fontes (DNS, WHOIS, dados abertos, geocodificação)
- [ ] Frontend de grafo (estilo Maltego)
- [ ] Testes e documentação de cada fonte

## Licença

MIT — veja [LICENSE](LICENSE).
