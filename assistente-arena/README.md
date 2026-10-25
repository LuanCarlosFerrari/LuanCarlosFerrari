# Assistente Arena

Companheiro para o **Magic: The Gathering Arena** no Windows. Ele **só lê e mostra informação**: nunca clica, nunca digita no jogo, nunca lê a memória do Arena e nunca joga por você.

> **Estado atual: protótipo da análise de tela (linha de comando).**
> Você aperta um atalho no construtor de decks e o Claude lê a tela, lista as cartas (nome em português e em inglês) e escreve um guia de como jogar o deck. Durante qualquer partida, a análise fica **bloqueada**.
> A especificação completa está em [`docs/spec.md`](docs/spec.md). A janela gráfica e o overlay vêm nas próximas fases, cada tela com um mock aprovado antes.

---

## 1. Instalação (Windows)

1. Instale o **uv**, o gerenciador de Python que equivale ao `npm` + `nvm`. Abra o PowerShell e rode:
   ```powershell
   winget install --id=astral-sh.uv -e
   ```
   Feche e abra o PowerShell de novo.
2. Baixe o projeto. Por enquanto ele está na pasta `assistente-arena/` do repositório do seu perfil, no branch `claude/sharp-maxwell-bvplvm`:
   ```powershell
   git clone -b claude/sharp-maxwell-bvplvm https://github.com/LuanCarlosFerrari/LuanCarlosFerrari.git
   cd LuanCarlosFerrari\assistente-arena
   uv sync
   ```
   O `uv sync` baixa o Python 3.12 (se precisar) e as dependências. É o equivalente a `npm install`.

## 2. Ativar o Registro Detalhado no Arena (obrigatório)

Sem ele, o log não tem os dados do jogo, e o programa não consegue saber se você está numa partida. Por segurança, a análise fica bloqueada.

1. No Arena, abra **Opções** (a engrenagem) → **Conta**.
2. Marque **Registro Detalhado (Suporte a plugins)**, em inglês *Detailed Logs (Plugin Support)*.
3. **Feche e abra o Arena de novo.**

Para conferir, rode `uv run assistente-arena status`. Deve aparecer `Registro Detalhado: ligado`.

## 3. Chave da API do Claude

A análise usa a API da Anthropic, que é **paga por uso**. Crie uma chave em <https://console.anthropic.com/> e depois rode:

```powershell
uv run assistente-arena chave
```

A chave fica guardada no **Gerenciador de Credenciais do Windows**, nunca num arquivo do projeto. Como alternativa, defina a variável de ambiente `ANTHROPIC_API_KEY`.

**Custo:** cada análise de tela custa por volta de **R$ 0,15 a R$ 0,30**. O programa mostra o valor de cada chamada e o total do mês em reais, com a cotação PTAX do Banco Central. O orçamento padrão é **R$ 20 por mês**: ao chegar em 80% o programa avisa, e ao chegar em 100% ele bloqueia.

## 4. Testar a ideia

Abra o Arena em **janela** ou **janela sem bordas**. Em tela cheia exclusiva, a captura pode sair preta.

### Opção A — atalho (recomendado)

```powershell
uv run assistente-arena observar --exportar
```

Deixe o terminal aberto, vá para o Arena, abra um deck no **construtor de decks** e aperte **Ctrl+Shift+A**. O resultado aparece no terminal:

- a lista de cartas reconhecidas, como `4x Tovolar, Soberano Medonho // Tovolar, Flagelo da Meia-noite (Tovolar, Dire Overlord // ...)`;
- marcações para o que precisa de atenção: `~` nome corrigido pelo Scryfall, `?` leitura incerta, `!` carta não encontrada;
- o guia **Como jogar este deck**: plano de jogo, mulligan, dicas e trocas sugeridas;
- com `--exportar`, a lista no formato de importação do Arena;
- o custo em R$.

Também vale testar:

- **Bloqueio na partida.** Entre numa partida (pode ser contra o computador) e aperte o atalho: deve aparecer `✖ Partida em andamento`. O terminal também avisa `▶ Partida iniciada` e `■ Partida encerrada`.
- **Coleção.** Abra a tela de **Coleção** e aperte o atalho. As cartas visíveis são listadas com as quantidades.

### Opção B — uma captura só

```powershell
uv run assistente-arena analisar --atraso 3
```

Você tem 3 segundos para trocar para a janela do Arena.

### Opção C — imagem salva

```powershell
uv run assistente-arena analisar --imagem C:\caminho\print-do-deck.png
```

### Outras opções

| Opção | O que faz |
|---|---|
| `--formato Padrão` | Formato que você pretende jogar (o padrão é Histórico). |
| `--json saida.json` | Salva a análise completa em JSON. |
| `--guardar-imagem tela.png` | Guarda a imagem enviada. Por padrão, ela é descartada. |
| `--atalho ctrl+shift+f9` | Troca o atalho (no comando `observar`). |

As configurações ficam em `%APPDATA%\AssistenteArena\config.json`: modelo, esforço, orçamento e cotação manual de reserva.

## 5. Comandos

| Comando | Para quê |
|---|---|
| `status` | Mostra se o log foi encontrado, o Registro Detalhado, se você está em partida, a chave e o gasto do mês. |
| `observar` | Fica em segundo plano e analisa ao apertar o atalho. |
| `analisar` | Faz uma análise agora (tela ou `--imagem`). |
| `chave` / `chave --remover` | Guarda ou remove a chave da API. |
| `log ARQUIVO` | Reproduz um `Player.log` e lista os eventos lidos. Serve para depurar o leitor. |

## 6. Se algo der errado

- **"Janela do MTG Arena não encontrada"**: o Arena precisa estar aberto e não minimizado.
- **"Não consegui confirmar pelo log..."**: ative o Registro Detalhado e reinicie o Arena.
- **Cartas lidas erradas**: imagens maiores ajudam. Use o Arena em tela maior ou dê zoom na lista do deck. O Scryfall corrige erros pequenos automaticamente (marcados com `~`).
- **Me ajude a melhorar o leitor do log**: rode `uv run assistente-arena log "%USERPROFILE%\AppData\LocalLow\Wizards Of The Coast\MTGA\Player.log"` depois de uma partida e me mande a saída ou o arquivo. Eu removo os dados pessoais antes de usar nos testes.

## 7. Para desenvolver

```powershell
uv run pytest           # testes
uv run ruff check src tests
uv run ruff format src tests
uv run mypy             # checagem de tipos (modo estrito)
```

### Python para quem vem do TypeScript

| TypeScript | Python neste projeto |
|---|---|
| `package.json` / `npm install` | `pyproject.toml` / `uv sync` |
| `npx tsc --noEmit` | `uv run mypy` |
| ESLint + Prettier | `ruff check` + `ruff format` |
| Jest / Vitest | `pytest` |
| `interface Carta { nome: string }` | `@dataclass class Carta: nome: str` |
| `string \| null` | `str \| None` |
| `import { x } from "./mod"` | `from assistente_arena.mod import x` |
| `zod` | `pydantic` (valida a resposta do Claude) |

### Organização

```
src/assistente_arena/
├── arena_log/   leitor do Player.log (isolado; quando o Arena mudar o formato, corrija aqui)
├── screen/      captura da janela, atalho global e o bloqueio durante partidas
├── cards/       Scryfall com cache (nomes em português e em inglês)
├── claude/      análise com o Claude e custos em reais
├── flow.py      junta tudo: bloqueio → orçamento → Claude → conferência
└── cli.py       comandos
```

`tests/test_regras.py` garante as regras do projeto: o teste falha se aparecer qualquer biblioteca ou chamada de automação de teclado e mouse ou de leitura de memória.
