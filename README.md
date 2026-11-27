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

## Uso ético

Use o PublicEye apenas para:

- Pesquisa acadêmica e jornalismo de interesse público
- Segurança defensiva e verificação de superfície de exposição **da própria organização**
- Educação em OSINT

Não use para assediar, constranger ou coletar dados pessoais de terceiros sem base legal.

## Roadmap

- [ ] Estrutura inicial do projeto
- [ ] Módulo de coleta com providers plugáveis
- [ ] Rate limiting e cache por provider
- [ ] Exportação de relatórios (JSON / Markdown)
- [ ] Testes e documentação de cada fonte

## Licença

MIT — veja [LICENSE](LICENSE).
