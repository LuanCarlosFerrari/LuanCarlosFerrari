# Assistente Arena — Especificação (v0.1, rascunho para aprovação)

> Status: **aguardando aprovação**. Nenhuma linha de código será escrita antes disso.
> Data: 25/10/2026.

---

## 1. Objetivo

O Assistente Arena é um programa para Windows que acompanha o Magic: The Gathering Arena. Ele **lê e mostra informação**: coleção, decks, estatísticas e, durante a partida, um overlay com os dados do grimório. Também ajuda a montar decks tribais e traz o Claude integrado para conversar sobre decks e analisar as partidas depois que elas acabam.

Público: um único usuário (você), que joga no PC, principalmente no Histórico, com decks tribais (hoje lobos e lobisomens com Tovolar, Soberano Medonho (Tovolar, Dire Overlord); em breve, zumbis).

Idioma: toda a interface em português do Brasil. Cartas aparecem com o nome em português e o inglês entre parênteses, por exemplo: **Gisa, Ressuscitadora Gloriosa (Gisa, Glorious Resurrector)**. Quando a carta não tem versão em português (cartas só digitais, Alquimia), aparece só o nome em inglês.

## 2. Regras que não podem ser quebradas

O programa **nunca**:

1. clica, digita ou envia qualquer comando ao jogo (nem simulação de teclado ou mouse direcionada ao Arena);
2. lê ou altera a memória do processo do Arena, injeta DLLs, intercepta tráfego de rede ou modifica arquivos do jogo;
3. decide jogadas no seu lugar.

Ele só **lê**: o arquivo `Player.log`, o banco de cartas que o Arena já deixa salvo no disco (se você aprovar, ver §5.3) e, quando você pede, **uma imagem da janela do Arena fora das partidas** (§9.5). Os arquivos são abertos em modo somente leitura; a captura de tela só copia pixels, como um programa de gravação faz, sem tocar no processo do jogo.

Para reforçar essas regras no código:

- não haverá nenhuma dependência de automação de entrada (`pyautogui`, `pynput` para envio, `SendInput` etc.) nem de leitura de memória (`pymem`, `ReadProcessMemory`). Um teste automatizado no CI vai falhar se alguma delas aparecer;
- os atalhos globais usam `RegisterHotKey` do Windows, que só **recebe** o atalho e não intercepta nem injeta teclas.

## 3. Decisões já tomadas

| Tema | Decisão |
|---|---|
| Repositório | Por enquanto, na subpasta `assistente-arena/` do repositório do seu perfil. Depois você move para um repositório próprio; o projeto não depende de nada fora da pasta. |
| Stack | Python + Qt (PySide6), como você escolheu. Detalhes e trade-offs em §4. |
| Sua experiência | Você vem de JS/TS. O código usa Python tipado (type hints em tudo, `mypy` estrito), o que deixa a leitura parecida com TypeScript. O README traz um "Python para quem vem do TS". |
| Claude durante a partida | **Não haverá dicas ao vivo.** O Claude atua só fora da partida: no montador de decks, nas perguntas sobre cartas e no resumo pós-partida. O overlay não terá painel do Claude. Veja §9.4. |
| Análise de tela | **Sim, sob demanda e só fora da partida.** Um botão ou atalho captura a janela do Arena no construtor de decks ou na coleção e manda a imagem ao Claude. Fica bloqueado automaticamente durante qualquer partida. Veja §9.5. |

## 4. Tecnologia

### 4.1 Comparação

| Critério | **Python + PySide6 (Qt)** | Tauri (Rust + web) | Electron |
|---|---|---|---|
| Overlay transparente e click-through | Nativo: `WindowTransparentForInput` + `WS_EX_TRANSPARENT` via `ctypes`. Bem documentado. | Possível (`set_ignore_cursor_events`), mas com WebView2 transparente há bugs conhecidos no Windows. | Funciona (`setIgnoreMouseEvents`), maduro. |
| Consumo (RAM) | ~80–150 MB | ~40–80 MB | ~200–400 MB |
| Impacto no FPS do jogo | Baixo: o overlay é desenhado pelo Qt só quando os dados mudam. | Baixo | Médio: o Chromium compõe a janela continuamente. |
| Linguagens a manter | 1 (Python) | 3 (Rust, TS, HTML/CSS) | 2 (TS, HTML/CSS) |
| Sua familiaridade | Nova linguagem, mas simples | TS conhecido, Rust novo | TS conhecido |
| Tamanho do instalador | ~60–100 MB | ~10 MB | ~100–150 MB |
| Ecossistema para o domínio | Excelente: SQLite, HTTP, testes, estatística (hipergeométrica) | Bom | Bom |

### 4.2 Recomendação: Python 3.12 + PySide6

É a stack que você escolheu, e eu também recomendo. O overlay é a parte mais delicada do projeto, e o Qt resolve transparência, "sempre por cima" e click-through com poucas linhas, sem a fragilidade do WebView transparente. Ter uma linguagem só facilita a manutenção. O custo é aprender Python, compensado pelos tipos estritos e por um código bem dividido em módulos.

Ferramentas:

- **Gerenciador de projeto:** `uv` (equivalente a `npm` + `nvm`). `pyproject.toml` faz o papel do `package.json`.
- **UI:** PySide6 (Qt 6, licença LGPL). As telas são widgets em Python, estilizadas com QSS (parecido com CSS).
- **Banco local:** SQLite (`sqlite3` da biblioteca padrão) para cache de cartas, coleção e histórico.
- **HTTP:** `httpx`, para o Scryfall e a cotação do dólar.
- **Claude:** SDK oficial `anthropic` para Python.
- **Chave da API:** `keyring`, que guarda a chave no Gerenciador de Credenciais do Windows. Alternativa: variável de ambiente `ANTHROPIC_API_KEY`.
- **Qualidade:** `pytest`, `ruff` (lint e formatação, como ESLint + Prettier) e `mypy --strict`.
- **Distribuição:** `PyInstaller` gera um `.exe` (pasta única). Também roda em modo desenvolvedor com `uv run assistente-arena`.

## 5. Fontes de dados

### 5.1 `Player.log` (fonte principal)

Caminho: `%USERPROFILE%\AppData\LocalLow\Wizards Of The Coast\MTGA\Player.log`. A sessão anterior fica salva em `Player-prev.log`.

**Registro Detalhado é obrigatório.** Na primeira execução, um assistente explica com imagens: *Arena → Opções (engrenagem) → Conta → marcar "Registro Detalhado (Suporte a plugins)" / "Detailed Logs (Plugin Support)" → reiniciar o Arena*. Se o programa detectar um log sem JSON de jogo, ele mostra um aviso persistente explicando o motivo.

**O que o log traz hoje** (segundo a pesquisa de out/2026, a confirmar com um log real seu, ver §12):

| Dado | Onde aparece (nomes atuais) | Observações |
|---|---|---|
| Ouro, gemas, curingas, progresso do cofre | `StartHook` → `InventoryInfo` (`Gold`, `Gems`, `WildCardCommons`, `WildCardUnCommons`, `WildCardRares`, `WildCardMythics`) | Só é atualizado quando o Arena abre. Mudanças durante a sessão podem chegar por eventos de atualização de inventário (a confirmar). |
| Decks | `StartHook` → `DeckSummariesV2` (nomes, formato) e listas de cartas por deck (a confirmar); salvamentos de deck aparecem como chamadas `==>`/`<==` | |
| Deck usado na partida | `greToClientEvent` → `ConnectResp` → `deckMessage.deckCards` (lista de `grpId`) | Confiável; é com ele que o rastreador do grimório funciona. |
| Início e fim da partida | `matchGameRoomStateChangedEvent` → `gameRoomInfo.stateType` (`MatchGameRoomStateType_Playing` / `_MatchCompleted`), `gameRoomConfig.reservedPlayers` (`systemSeatId`, `playerName`), `finalMatchResult.resultList` | |
| Estado do jogo | `greToClientEvent.greToClientMessages[]` → `GREMessageType_GameStateMessage` → `gameObjects`, `zones`, `turnInfo`, `annotations`, `diffDeletedInstanceIds` | Mensagens são **deltas**; um evento pode trazer várias. Anotações usam `snake_case` (`zone_src`, `zone_dest`, `orig_id`, `new_id`). |
| Resultado de cada jogo | `gameInfo.stage = GameStage_GameOver` + `matchState = MatchState_GameComplete` → `results[]` (`winningTeamId`) | Cada fim de jogo gera duas mensagens; filtrar para não contar duplicado. |
| Ranque | `RankGetCombinedRankInfo` | |
| **Coleção completa** | **Não aparece mais no log** (`GetPlayerCardsV3` foi removido em ago/2021). | **Ponto crítico, ver §5.4.** |

### 5.2 Leitor do log (módulo isolado)

Pacote `arena_log/`, que **não depende de Qt** e por isso pode ser testado e corrigido sozinho. Ele tem três camadas:

1. **`tailer.py` — acompanhar o arquivo.**
   - Lê só o que foi acrescentado, verificando o arquivo a cada 250 ms (o custo é desprezível).
   - Abre o arquivo pela API do Windows (`CreateFileW`) com `FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE`. Isso é **essencial**: se o programa segurasse o arquivo sem permitir exclusão, poderia impedir o Arena de renomear o log para `Player-prev.log` ao abrir.
   - Detecta que o arquivo foi recriado (tamanho menor que a posição atual ou outro ID de arquivo) e recomeça do início, emitindo um evento `LogReset`.
   - Na inicialização, relê o log atual inteiro para recuperar o estado (inventário, partida em andamento).
   - Roda numa thread separada e entrega os dados à interface por um sinal Qt. A interface nunca trava.
2. **`framing.py` — separar entradas.** Junta linhas até o próximo cabeçalho `[UnityCrossThreadLogger]` e extrai o JSON contando chaves e respeitando strings. Faz uma segunda leitura do JSON quando o conteúdo vem escapado dentro de `request`. Também casa cada `==>` com seu `<==` pelo `id`.
3. **`handlers/` — interpretar.** Há um handler por tipo de mensagem (`start_hook.py`, `match_room.py`, `gre.py`, `inventory.py`, ...), registrado num dicionário. Cada um transforma JSON em **eventos tipados** (`dataclasses`): `InventoryUpdated`, `DecksLoaded`, `MatchStarted`, `GameStateDelta`, `GameEnded`, `MatchEnded`.

Quando o formato mudar, a correção fica restrita a um handler. Para isso:

- cada handler acessa os campos de forma tolerante: campo ausente gera um aviso, não derruba o programa;
- há um contador de falhas de leitura por tipo de mensagem, visível em *Configurações → Diagnóstico*. Um número diferente de zero indica que o Arena mudou o formato;
- a ferramenta `uv run arena-log replay arquivo.log` reproduz um log e imprime os eventos. Ela serve para depurar e para gerar novos testes.

**Testes:** `tests/fixtures/` guarda trechos reais e anonimizados (sem `userId` e `playerName`), com um teste por handler, além de casos de recriação do arquivo, JSON em várias linhas, mensagens agrupadas e campos ausentes.

### 5.3 Dados das cartas

Na partida, o log identifica cada carta por um número, o `grpId`, que é o ID do Arena. O caminho até os dados completos é:

1. **Scryfall (principal).**
   - `GET /cards/arena/{grpId}` → carta em inglês (custo, tipo, texto, raridade, legalidades, imagem, `oracle_id`).
   - Busca `oracleid:{id} lang:pt` com `include_multilingual=true` → nome em português (`printed_name`; em cartas dupla-face, `card_faces[].printed_name`). Exemplo verificado: `78613` → Tovolar, Soberano Medonho // Tovolar, Flagelo da Meia-noite.
   - Boas práticas da API: cabeçalhos `User-Agent` e `Accept`, no máximo cerca de 10 requisições por segundo (uso 100 ms entre chamadas) e cache local.
   - Para o montador de decks (Fase 2), baixo uma vez por semana o *bulk data* `oracle_cards` (~160 MB, uma entrada por carta), que inclui `arena_id`, legalidades e tipos. Assim as buscas por tribo ficam locais e rápidas.
2. **Cache local:** SQLite `cards.db` com os dados por carta e o nome em português, mais as imagens em `cache/images/`. Uma carta já vista nunca é buscada de novo. O cache é renovado a cada 30 dias, ou na hora, por um botão.
3. **Opcional, precisa da sua aprovação:** o banco de cartas que o próprio Arena salva no disco (`MTGA_Data\Downloads\Raw\Raw_CardDatabase_*.mtga`, um SQLite com nomes localizados). É só leitura de arquivo, como o `Player.log`, e não toca no processo. A vantagem é cobrir cartas lançadas ontem, antes de chegarem ao Scryfall.

### 5.4 Coleção — decisão necessária

Como o log não traz mais a coleção completa, e lê-la da memória do jogo está proibido pelas regras (§2), proponho a **"coleção conhecida"**, montada por camadas:

- **A. Automática pelo log:** toda carta que está num deck seu é uma carta que você tem (na quantidade usada). Somam-se as cartas ganhas que aparecerem nas atualizações de inventário durante a sessão.
- **B. Importação manual:** colar uma lista em texto (formato do Arena ou `4 Nome`) ou importar um CSV. Uma forma prática de exportar tudo é criar no Arena um deck temporário com todas as cartas de um filtro (por exemplo, tipo "Lobo") e exportar.
- **C. Edição manual:** marcar na tela "tenho 2 cópias" de uma carta.
- **D. Leitura da tela (Fase 3B):** você abre as páginas da coleção no Arena e aciona "Analisar tela". O Claude reconhece as cartas e as quantidades, o programa confere cada nome no Scryfall e você confirma antes de salvar (§9.5).

A tela de coleção mostra de onde veio cada informação, e o montador avisa: *"a coleção pode estar incompleta"*.

## 6. Funcionalidades por fase

Cada fase começa com um **mock HTML estático** para você aprovar (o que valer para a fase) e termina com um roteiro "como testar".

### Fase 0 — Fundação (sem interface)
- Esqueleto do projeto, `pyproject.toml`, CI com lint, tipos e testes.
- Leitor do log completo (§5.2) com testes, mais o comando `arena-log replay`.
- Cliente do Scryfall com cache.
- **Como testar:** `uv run arena-log replay "%USERPROFILE%\AppData\LocalLow\Wizards Of The Coast\MTGA\Player.log"` mostra inventário, decks e partidas no terminal.

### Fase 1 — Coleção e decks (janela principal)
- Painel com ouro, gemas, curingas por raridade e progresso do cofre.
- Coleção conhecida (§5.4), com busca e filtros por cor, tipo, raridade e tribo.
- Lista de decks. Para cada deck:
  - **curva de mana** (gráfico de barras de 0 a 7+, separando criaturas de outras mágicas);
  - **cores:** símbolos de mana por cor e fontes de mana por cor;
  - **terrenos e geradores de mana**: terrenos; criaturas e artefatos com habilidade de gerar mana (detectada no texto: `{T}: Add`);
  - **alertas:**
    - deck com menos de 60 cartas (ou de 40/100, conforme o formato) ou com mais de 60 (aviso leve: "acima de 60 reduz a consistência");
    - mana demais ou de menos: comparo os terrenos com o recomendado pelo custo médio, `terrenos ≈ 17 + (CMC médio − 2) × 2,5` (16 a 27 em 60 cartas), com tolerância de ±2;
    - fontes de cada cor abaixo do mínimo recomendado para os custos do deck (tabela de Karsten simplificada).
- Primeira execução: assistente do Registro Detalhado.

### Fase 2 — Montador de decks
- Entradas: **tribo** (Lobo, Lobisomem, Zumbi, Elfo, Vampiro..., com o nome em português e o subtipo em inglês), **formato** (Histórico, Padrão, Explorador, Atemporal, Brawl Histórico) e, opcionalmente, cores e uma carta-chave (ex.: Tovolar).
- Algoritmo **determinístico e local** (não depende do Claude, funciona offline):
  1. reúne as cartas legais no formato que **são** da tribo (subtipo ou Changeling) ou que **citam** a tribo no texto (lordes, recompensas);
  2. dá pontos a cada carta: sinergia tribal + qualidade (custo-benefício para a curva) + **bônus por você já ter a carta**;
  3. preenche um modelo de curva (por exemplo, 2/8/8/6/4/2 mágicas de 1 a 6+, ajustável) e uma base de terrenos de acordo com as cores, usando os terrenos que você já tem;
  4. para cada carta, gera uma **explicação curta** a partir de regras ("Lorde: dá +1/+1 aos seus Lobisomens", "Remoção barata nas cores do deck", "Você já tem 4").
- **Curingas faltando** por raridade, comparando com os que você tem ("Faltam 3 raros: você tem 5, sobram 2").
- **Exportar/importar** no formato do Arena (`Deck` / `4 Tovolar, Dire Overlord (MID) 170` / linha em branco / `Sideboard`). A exportação usa nomes em inglês com coleção e número, que o Arena aceita em qualquer idioma do cliente.

### Fase 3 — Overlay
- Janela sem borda, transparente, sempre por cima e **click-through** (o clique passa para o jogo). Flags Qt: `FramelessWindowHint | WindowStaysOnTopHint | Tool | WindowTransparentForInput`, mais `WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW` via Win32. A janela não aparece na barra de tarefas nem rouba o foco.
- **Conteúdo durante a partida:**
  - **Meu grimório:** quantidade de cartas restantes. Por carta: cópias restantes e chance de comprá-la no próximo turno.
    - Restantes = lista do deck − cartas que já saíram do grimório (mão, campo, cemitério, exílio, reveladas). Quando o jogo embaralha ou move uma carta escondida, a contagem é recalculada pelo tamanho da zona.
    - Chance na próxima compra = cópias / tamanho do grimório. Se houver mais de uma compra, uso a hipergeométrica: P(≥1) = 1 − C(N−k, n)/C(N, n).
    - Agrupamento opcional por tipo ("terrenos: 9 restantes — 41% de comprar um").
  - **Adversário:** cartas que ele já jogou ou revelou (só as que ficaram visíveis), em ordem, com quantidade.
- **Atalhos padrão** (configuráveis): `Ctrl+Shift+O` mostra/esconde; `Ctrl+Shift+P` alterna a posição (direita → esquerda → oculto); `Ctrl+Shift+L` destrava o overlay para arrastar, porque o click-through impede o mouse; `Ctrl+Shift+L` de novo trava.
- **Janela do jogo:** acompanha a posição e o tamanho da janela do `MTGA.exe` e se ancora a ela. Se o jogo estiver em **tela cheia exclusiva** (detectada por `SHQueryUserNotificationState = QUNS_RUNNING_D3D_FULL_SCREEN` e pelo retângulo da janela), avisa na janela principal e numa notificação: *"Use Janela sem bordas nas configurações gráficas do Arena para ver o overlay."*
- **Leveza:** o overlay só é redesenhado quando chega um evento novo, sem laço de animação. Meta: < 1% de CPU e < 150 MB de RAM no programa inteiro durante a partida.

### Fase 3B — Claude integrado (fora da partida)
Detalhada em §9: montador e perguntas sobre cartas, resumo pós-partida e **análise de tela** do construtor de decks e da coleção (§9.5).
- **Como testar:** com o Arena aberto no construtor de decks, aperte o atalho "Analisar tela" e confira a lista reconhecida e o guia do deck. Depois, entre numa partida e verifique que o botão fica desativado.

### Fase 4 — Extras
- **Histórico de partidas** (SQLite): data, deck, formato, adversário (nome e cores e arquétipo inferidos das cartas vistas), resultado por jogo e por partida, quem começou, mulligans. Taxas de vitória por deck, por cores do adversário e por "na mão / no empate".
- **Lista de compras física:** a partir de um deck, gera a lista com nome em português e em inglês, coleção e quantidade, e um **link de busca na LigaMagic** para cada carta (`ligamagic.com.br/?view=cards/search&card=<nome>`). O programa **não** busca preços automaticamente (a LigaMagic não tem API pública, e raspar o site é frágil e pode violar os termos dela). Você pode digitar o preço em **R$** ao lado de cada carta, e o programa soma o total em reais. Nenhum valor aparece em dólar.

## 7. Arquitetura

```
assistente-arena/
├── pyproject.toml
├── README.md
├── docs/
│   ├── spec.md
│   └── mocks/                 # HTML estáticos para aprovação
├── src/assistente_arena/
│   ├── arena_log/             # leitor do log — sem Qt, isolado (§5.2)
│   │   ├── tailer.py
│   │   ├── framing.py
│   │   ├── events.py          # dataclasses dos eventos
│   │   └── handlers/
│   ├── game/                  # estado da partida, grimório, probabilidades
│   ├── cards/                 # Scryfall, cache, nomes PT/EN
│   ├── collection/            # coleção conhecida, decks, análise de mana
│   ├── builder/               # montador de decks, import/export
│   ├── claude/                # cliente, montagem de contexto, custos
│   ├── screen/                # captura da janela do Arena (bloqueada durante partidas)
│   ├── storage/               # SQLite, migrações
│   ├── config/                # configurações locais e chave da API
│   ├── ui/
│   │   ├── theme.qss
│   │   ├── main_window/
│   │   └── overlay/           # janela click-through, hotkeys, detecção da janela do jogo
│   └── app.py
└── tests/
    ├── fixtures/              # trechos de Player.log anonimizados
    └── ...
```

Fluxo:

```
Player.log ─▶ tailer (thread) ─▶ framing ─▶ handlers ─▶ eventos tipados
                                                          │
                ┌─────────────────────────────────────────┤
                ▼                     ▼                   ▼
          collection/inventário   game/estado        storage/histórico
                │                     │                   │
                └──────────▶ ui (janela principal / overlay) ◀── cards (Scryfall + cache)
                                      │
                                 claude/ (sob demanda, fora da partida)
```

Princípio: tudo que interpreta dados (`arena_log`, `game`, `collection`, `builder`, `claude/context`) é Python puro, testável sem Windows e sem interface. Só `ui/` e o `tailer` dependem de recursos do Windows.

Dados locais em `%APPDATA%\AssistenteArena\` (configurações, `cards.db`, `historico.db`, imagens). Nada disso fica dentro do repositório.

## 8. Visual

Estilo industrial e minimalista. Ponto de partida da paleta (ajustável nos mocks):

| Papel | Cor |
|---|---|
| Fundo (carvão) | `#1C1D1A` |
| Superfície | `#262722` |
| Borda / divisor | `#3A3B34` |
| Destaque (verde oliva) | `#7A8450` |
| Destaque forte | `#9AA36A` |
| Terroso (alertas suaves) | `#A9773F` |
| Erro (ferrugem) | `#A4452C` |
| Texto | `#E4DFD3` |
| Texto secundário | `#9C978A` |

- Tipografia: **Inter** para a interface e **JetBrains Mono** para números e porcentagens, que ficam alinhados em colunas.
- Cantos de 2–4 px, sem sombras pesadas nem gradientes, ícones de traço fino.
- **Overlay:** fundo carvão com 80–85% de opacidade (ajustável), texto claro com contraste ≥ 7:1, largura de cerca de 260 px, fonte de 13–14 px, sem animações. Porcentagens em oliva; destaque terroso para "carta-chave ainda no grimório".

## 9. Integração com o Claude (Fase 3B)

### 9.1 Usos
1. **Montador de decks:** sugerir cortes e trocas (sempre preferindo cartas que você tem), explicar sinergias e responder perguntas sobre cartas e regras.
2. **Resumo pós-partida:** ao fim de cada partida, se você ativar, ou com um botão. Mostra o que funcionou, o que deu errado (inundação de mana, falta de mana, cartas que ficaram presas na mão) e sugestões de ajuste no deck.
3. **Análise de tela** no construtor de decks e na coleção (§9.5): guia de como jogar o deck, sugestões de troca e reconhecimento da coleção.
4. **Nada durante a partida** (decisão sua, ver §9.4).

### 9.2 Contexto enviado (mínimo necessário)
- Deck atual: lista compacta (`4x Nome EN`) e formato.
- Coleção: **só** as cartas relevantes à pergunta (da tribo e das cores do deck), não a coleção inteira.
- Pós-partida: um resumo do jogo gerado localmente (turno a turno: terrenos baixados, mágicas jogadas por cada lado, vida, resultado), não o log bruto.
- Texto das cartas: só das cartas citadas, obtido do cache do Scryfall.
- Análise de tela: só a imagem da janela do Arena (nunca a tela inteira), reduzida para no máximo 1568 px no lado maior, mais o contexto de texto acima.
- Nenhum dado de identidade (nome do adversário, `userId`) é enviado.

### 9.3 Modelo, custo e limites
- Modelo padrão: **Claude Opus 5.5** (`claude-opus-5-5`), com opção de trocar para Sonnet 5.5 (`claude-sonnet-5-5`) ou Haiku 5.5 (`claude-haiku-5-5`), que são mais baratos, em *Configurações*. Uso streaming para a resposta aparecer enquanto é gerada.
- Preços de referência da API (em dólar por milhão de tokens, convertidos para reais na tela): Opus 5.5 entrada 4 / saída 20 / leitura de cache 0,20; Sonnet 5.5 entrada 2 / saída 10; Haiku 5.5 entrada 0,10 / saída 0,50.
- **Tudo é mostrado em R$.** A cotação vem da API pública do Banco Central (PTAX), atualizada uma vez por dia, com um valor manual de reserva.
  - Exemplo: um resumo pós-partida com cerca de 6 mil tokens de entrada e 800 de saída no Opus 5.5 custa cerca de US$ 0,04, ou **≈ R$ 0,22** com o dólar a R$ 5,50.
  - Exemplo: uma análise de tela (imagem de ~1568×882 ≈ 1.850 tokens + ~1.500 de contexto, ~1.200 de resposta) custa cerca de US$ 0,04, ou **≈ R$ 0,20**.
  - Antes de cada chamada, o programa mostra uma estimativa ("≈ R$ 0,20"). Depois, mostra o custo real, calculado com o `usage` devolvido pela API.
- **Cache:**
  - *prompt caching* da API: instruções fixas + deck + coleção relevante formam um prefixo estável, então perguntas seguidas sobre o mesmo deck pagam bem menos;
  - cache local de respostas: a mesma pergunta sobre o mesmo deck não é reenviada.
- **Limites:**
  - **orçamento mensal em R$** (padrão R$ 20). Ao atingir 80%, o programa avisa; ao atingir 100%, bloqueia até você liberar;
  - chamadas automáticas (só o resumo pós-partida) limitadas a 1 por partida e no máximo 10 por hora;
  - painel de gastos por dia e por mês.
- **Chave da API:** guardada no Gerenciador de Credenciais do Windows (`keyring`) ou lida de `ANTHROPIC_API_KEY`. Nunca é escrita em arquivo do projeto. O `.gitignore` bloqueia `.env` e arquivos de configuração locais, e o CI roda um verificador de segredos.

### 9.4 Termos de uso da Wizards — o que a pesquisa encontrou
- Não encontrei nenhuma regra oficial e atual da Wizards que trate especificamente de assistência por IA durante partidas ranqueadas. Os termos (EULA) e as regras de torneios proíbem trapaça, manipulação do cliente e práticas desleais, mas não detalham ferramentas de terceiros.
- Rastreadores de deck baseados no log (Untapped.gg, 17Lands, Arena Tutor) são tolerados há anos. O argumento é que só mostram informação que o jogador já tem, e o próprio log existe com a opção "Suporte a plugins".
- Já uma IA sugerindo jogadas ou lendo o que o adversário "pode ter na mão" em tempo real é uma zona cinzenta, mais próxima de "assistência externa". Por isso a sua decisão de **manter o Claude só fora da partida** é a mais segura. O overlay mostra apenas contagens e probabilidades calculadas do seu próprio grimório e as cartas que o adversário já mostrou, como os rastreadores conhecidos.
- Se a Wizards publicar uma regra clara permitindo, a função pode ser reavaliada numa versão futura, sempre desligada por padrão no ranqueado.

### 9.5 Análise de tela (fora da partida)
- **Quando:** só quando você pede, por um botão na janela principal ou pelo atalho `Ctrl+Shift+A`. Não existe captura contínua nem automática.
- **Bloqueio na partida:** o leitor do log sabe quando uma partida começa e termina (`MatchStarted` / `MatchEnded`). Nesse intervalo a captura fica **desativada no código**, e não só escondida na interface, e o atalho mostra "indisponível durante a partida". Se o log não estiver legível, por exemplo sem o Registro Detalhado, a captura também fica bloqueada, por segurança.
- **O que é capturado:** só a janela do `MTGA.exe`, pela API de captura do Windows (Windows Graphics Capture, com `mss` como alternativa). Funciona em janela e em janela sem bordas.
- **Usos:**
  1. *Construtor de decks:* o Claude identifica o deck em edição, mesmo antes de ser salvo, e devolve:
     - um **guia de como jogar o deck**: plano de jogo, mulligan, cartas para segurar, combinações e ameaças típicas do formato;
     - sugestões de troca, priorizando cartas da sua coleção.
  2. *Coleção:* reconhece cartas e quantidades das páginas visíveis e propõe acrescentá-las à coleção conhecida (§5.4, camada D).
- **Precisão:** a resposta do Claude vem em formato estruturado (lista de `{nome, quantidade}`). Cada nome é conferido no cache do Scryfall (em português e em inglês) e, quando possível, com o deck salvo no log. O que não bater aparece destacado para você corrigir, e nada entra na coleção sem a sua confirmação.
- **Privacidade:** a imagem fica só na memória e é descartada depois da análise (ver pergunta 9 em §12). Nada é salvo no repositório.

## 10. Testes e qualidade
- `pytest` cobre: framing, cada handler (com fixtures reais anonimizadas), recriação do arquivo, estado da partida (contagem do grimório em cenários com embaralhar, vidência e exílio), probabilidades, análise de mana, montador e import/export.
- Teste de "regras invioláveis": falha se aparecer dependência ou chamada de automação de entrada ou de leitura de memória.
- Teste do bloqueio da análise de tela: com uma partida em andamento no log reproduzido, a captura tem de ser recusada.
- CI no GitHub Actions (Windows e Linux): `ruff`, `mypy --strict`, `pytest`.
- Testes manuais no Windows ao fim de cada fase, com roteiro no README. O desenvolvimento acontece em Linux, então a parte específica do Windows (overlay, hotkeys, `CreateFileW`) **depende do seu teste**.

## 11. Entregáveis
- Código em `assistente-arena/` com um histórico Git limpo, pronto para virar repositório próprio.
- `README.md` em português: instalação (`.exe` ou `uv`), como ativar o Registro Detalhado, uso de cada tela, atalhos, configuração da chave do Claude, solução de problemas e "Python para quem vem do TS".
- `docs/mocks/*.html`: um por tela, aprovado antes da implementação.

## 12. Perguntas em aberto (preciso das suas respostas)
1. **Coleção (§5.4):** você aceita a "coleção conhecida" (decks + importação + edição manual + leitura da tela)? Prefere outro caminho?
2. **Amostra do log:** você pode me mandar um `Player.log` real, depois de jogar 1 ou 2 partidas com o Registro Detalhado ligado? Eu anonimizo antes de usar nos testes. Sem ele, os handlers ficam baseados em documentação de terceiros e podem errar nomes de campos.
3. **Banco de cartas do Arena no disco (§5.3, item 3):** posso ler esse arquivo, que é só leitura, como o log?
4. **Formatos:** além do Histórico, quais você quer no montador? Partidas melhor de 1, melhor de 3 ou ambas?
5. **Idioma do cliente do Arena:** está em português? Isso só afeta a mensagem de ajuda (nomes dos menus).
6. **Modelo padrão do Claude:** mantenho o Opus 5.5 ou prefere começar com um mais barato?
7. **Orçamento mensal padrão:** R$ 20 está bom?
8. **Atalhos e posição do overlay:** os padrões de §6 (Fase 3) servem? Lado direito da tela por padrão?
9. **Imagens capturadas:** apago cada imagem logo depois da análise (padrão proposto) ou guardo as últimas para você rever?

---

### Fontes consultadas
- [Everything We Know About the MTG Arena Log File in 2026 (Manasight)](https://blog.manasight.gg/arena-log-format-guide/)
- [MTG-Arena-Tracker (Shalkith)](https://github.com/Shalkith/MTG-Arena-Tracker) — parser de referência para `InventoryInfo` e `deckMessage`
- [Creating Log Files on PC/Mac/Steam (suporte Wizards)](https://mtgarena-support.wizards.com/hc/en-us/articles/360000726823-Creating-Log-Files-on-PC-Mac-Steam)
- [How does the Untapped.gg Companion work](https://help.hearthsim.net/en/articles/5020719-how-does-the-untapped-gg-companion-work)
- [Magic: The Gathering Arena EULA](https://store.steampowered.com/eula/2141910_eula_0)
- [MTG Arena Tool](https://github.com/CodySchrank/MTG-Arena-Tool) e [Aetherhub — Why you should use MTG Arena Deck Trackers](https://aetherhub.com/Article/Why-you-should-use-MTG-Arena-DeckTrackers)
- API do Scryfall (`/cards/arena/{id}` e busca com `lang:pt`), testada em 25/10/2026.
