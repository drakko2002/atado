# SPEC B — `atado reconstruct`: Reconstrução de contexto via agente de IA (pesquisa profunda + entrevista)

> Extensão da SPEC A (`atado`). Pré-requisito: fases F0–F5 concluídas.
> Documento para execução pelo Claude Code (Opus 4.8). Ler inteiro antes de codificar. Executar fase por fase (F6–F10).

---

## 1. Objetivo

A SPEC A produz um corpus transcrito, diarizado e um índice de termos — mas o **significado** das siglas e o **contexto geral da reunião** continuam fragmentados. A SPEC B adiciona a etapa de **reconstrução**: um agente de IA recebe o corpus, conduz **pesquisa profunda** sobre os termos observados (instituições, plataformas, siglas) e **entrevista o usuário** para preencher o que a pesquisa não resolve, produzindo ao final:

1. Uma **narrativa reconstruída** da reunião (o que foi discutido, decidido, pendências).
2. A **tabela de termos resolvida** (a tabela do usuário: sigla → significado), com **nível de confiança e proveniência** de cada resposta.
3. Um **registro da entrevista** e uma lista de **questões em aberto**.

O agente é **plugável**: Claude, GPT, Gemini, ou modelo local — o usuário escolhe. O caminho principal (v1) é **agent-agnóstico por design**: o `atado` prepara um pacote que funciona em qualquer chat de IA, sem integração de API. Integração via API é fase posterior e opcional.

## 2. Princípio central: dois modos, kit primeiro

### Modo 1 — Kit portátil (`atado kit`) — OBRIGATÓRIO na v1
O `atado` gera um diretório `out/kit/` autocontido que o usuário leva ao agente da sua preferência (upload de arquivos ou colagem no chat). O kit contém o **protocolo de reconstrução** (instruções que transformam qualquer LLM capaz no "agente reconstrutor") + os dados. Nenhuma chave de API, nenhuma dependência nova, funciona com claude.ai, ChatGPT, Gemini, ou LLM local com contexto suficiente.

**Racional:** o usuário declarou que usará o Claude no chat. Agentes de chat modernos já têm busca na web e upload de arquivos — a engenharia está em preparar dados e protocolo, não em reimplementar o chat.

### Modo 2 — Integração via API (`atado reconstruct --provider ...`) — fase posterior (F9)
Sessão interativa no terminal: o `atado` chama a API do provedor escolhido, o agente pesquisa (quando o provedor oferece ferramenta de busca) e entrevista o usuário no próprio terminal. Provedores-alvo: `anthropic`, `openai`, `gemini`, `ollama` (este sem busca — degrada para pesquisa mediada pelo usuário, ver §6.3).

## 3. Conteúdo do kit (`out/kit/`)

```
kit/
├── 00_PROTOCOLO.md          # instruções para o agente (o "prompt de sistema" portátil)
├── 01_contexto_usuario.md   # gerado do atado.yaml + respostas prévias (context.yaml)
├── 02_termos.md             # índice de termos com ocorrências e janelas de contexto
├── 03_transcricao.md        # corpus consolidado (versão compacta, com speakers/timestamps)
├── 04_suspeitos.md          # saída do `atado suspects`
└── LEIA-ME.txt              # instruções para o usuário humano (como usar o kit em cada agente)
```

Regras de geração:
- Tamanho-alvo do kit: caber em ~150k tokens; se exceder, `atado kit --compact` remove falas curtas de baixa informação (interjeições, confirmações) e trunca janelas de contexto, **nunca** removendo ocorrências de termos rastreados.
- `01_contexto_usuario.md` inclui: descrição do projeto, glossário atual (com o que já se sabe), instituições envolvidas, e a **tabela de siglas do usuário no estado atual** (colunas: sigla, palpite, timestamps, significado=???).
- Tudo em PT-BR.

## 4. O Protocolo de Reconstrução (`00_PROTOCOLO.md`)

Este arquivo é o coração da SPEC B: um documento de instruções que o Claude Code deve **escrever com cuidado** (é um prompt operacional, não código). Ele instrui o agente a executar o seguinte processo:

### Fase R1 — Ingestão e triagem
- Ler todos os arquivos do kit antes de qualquer pergunta.
- Classificar cada termo em: **(a) resolvível por pesquisa** (nome público — instituição, plataforma, lei), **(b) resolvível por contexto interno** (dedutível da própria transcrição), **(c) requer o usuário** (jargão interno, provável erro de transcrição, referência pessoal).
- Apresentar ao usuário um **plano de reconstrução** curto: o que vai pesquisar, o que vai perguntar, em que ordem.

### Fase R2 — Pesquisa profunda
- Para termos classe (a): usar busca na web. Priorizar fontes primárias (sites institucionais .gov.br, .edu.br, páginas oficiais de plataformas). Ex.: "CETEC IFRS", "PROSAS plataforma editais", "CIAP IFRS".
- Cada achado vira uma **hipótese com evidência citada** (URL/fonte), nunca afirmação definitiva — a confirmação final considera se a hipótese é compatível com as ocorrências na transcrição.
- Se o agente não tiver busca (modelo local), esta fase vira **pesquisa mediada**: o agente fornece ao usuário as queries exatas a pesquisar e pede os resultados de volta.

### Fase R3 — Entrevista (regras rígidas)
O agente entrevista o usuário para resolver classes (b) e (c) e validar hipóteses de (a). Regras que o protocolo deve impor:

1. **Lotes pequenos**: no máximo 3–4 perguntas por rodada. Nunca despejar um questionário inteiro.
2. **Priorização por impacto**: perguntar primeiro o que desbloqueia mais contexto (ex.: "quem é 'a nossa secretaria'?" resolve CETEC e reordena outras hipóteses).
3. **Perguntas ancoradas em evidência**: toda pergunta cita a ocorrência ("Em audio_03 @ 28:18, alguém diz '...o ORSID vai avaliar...'. Isso soa como outro nome pra você? Poderia ser 'o RSI', 'o CID', outra coisa?").
4. **Oferecer hipóteses, não pedir redação**: sempre que possível, apresentar 2–3 alternativas para o usuário escolher/corrigir — é mais rápido do que resposta aberta.
5. **Aceitar "não sei"**: registrar como questão em aberto e seguir; nunca insistir.
6. **Checkpoint de memória**: ao fim de cada rodada, resumir o que foi estabelecido ("Confirmado: CGD = Comitê Gestor de Dados; hipótese forte: CETEC = ...") antes da próxima rodada.
7. **Suspeitas de erro de transcrição** (ORSID, MEITUS): tratar como problema fonético — propor candidatos por similaridade sonora em PT-BR e, se resolvido, instruir o usuário a atualizar o `glossary` do `atado.yaml` (aliases) e retranscrever se valer a pena.
8. **Encerramento pelo usuário**: o usuário pode dizer "encerrar entrevista" a qualquer momento; o agente então sintetiza com o que tem.

### Fase R4 — Síntese e entregáveis
O protocolo instrui o agente a produzir, ao final, três blocos claramente delimitados (para o usuário salvar ou para o `atado interview import` parsear):

1. **`TABELA_RESOLVIDA`** — markdown table: `| Sigla | Significado | Confiança | Proveniência |`
   - Confiança: `confirmada` (usuário confirmou) / `alta` (fonte primária + compatível com transcrição) / `média` / `baixa` (especulação declarada).
   - Proveniência: `usuário`, `web:<fonte>`, `transcrição @ ref`, ou combinação.
2. **`NARRATIVA`** — reconstrução da reunião em prosa: pauta aparente, discussões por tema (com refs `arquivo @ mm:ss`), decisões, encaminhamentos, responsáveis (por speaker/nome quando identificado).
3. **`PENDENCIAS`** — questões em aberto + sugestões de próxima ação (retranscrever com glossário atualizado, perguntar a participante X, etc.).

Regra de ouro do protocolo (escrever explicitamente): **o agente nunca apresenta especulação como fato**; tudo que não for confirmado carrega marcador de confiança, e a narrativa distingue "dito na reunião" de "inferido".

## 5. Fechamento do loop com a SPEC A

- `atado interview import <arquivo.md>`: o usuário salva a saída final do agente num arquivo; o comando parseia os blocos `TABELA_RESOLVIDA` e `PENDENCIAS` e:
  - atualiza `glossary.terms[].meaning` e `aliases` no `atado.yaml` (com backup do anterior);
  - grava `out/context.yaml` (conhecimento acumulado: fatos confirmados, hipóteses, pendências) — que alimenta o próximo `atado kit`, tornando o processo **iterativo**: transcreve → kit → reconstrução/entrevista → import → (opcional) retranscreve com glossário melhor → kit v2...
- Parser tolerante: blocos identificados por cabeçalhos-sentinela (`### TABELA_RESOLVIDA` etc.); se a IA variar o formato, falhar com mensagem indicando o trecho problemático, nunca corromper o `atado.yaml`.

## 6. Modo 2 — Integração via API (F9, opcional)

### 6.1 Abstração de provedor
- `providers/base.py`: `Protocol` mínimo — `chat(messages, tools) -> reply` com suporte a streaming; sem framework pesado (não usar LangChain).
- Adapters: `anthropic` (SDK oficial, ferramenta `web_search` nativa da API), `openai` (Responses API com busca), `gemini` (grounding), `ollama` (sem busca → protocolo degrada para pesquisa mediada, §4-R2).
- Chaves via env (`ANTHROPIC_API_KEY` etc.), nunca no `atado.yaml`.

### 6.2 Sessão interativa
- `atado reconstruct --provider anthropic --model claude-opus-4-8`: REPL no terminal com `rich`; o agente segue o mesmo `00_PROTOCOLO.md` (single source of truth — o protocolo é injetado como system prompt); respostas do usuário viram o lado humano da entrevista; sessão salva em `out/sessions/<timestamp>.json` (retomável com `--resume`).
- Ao final, os três blocos são gravados automaticamente e o `interview import` é oferecido.

### 6.3 Degradação sem busca
Quando o provedor não tem ferramenta de busca, o agente emite blocos `PESQUISAR: <query>` e o CLI pausa pedindo que o usuário cole resultados — comportamento definido no protocolo, não no código.

## 7. Privacidade e consentimento (obrigatório)

A SPEC A é local-first; a SPEC B **envia conteúdo da reunião a terceiros**. Requisitos:

1. `atado kit` e `atado reconstruct` exibem aviso claro de que o conteúdo sairá da máquina, exigindo confirmação (`--yes` para pular em automação).
2. `atado kit --redact`: passe opcional de redação antes da geração — substitui padrões de PII (CPF, e-mails, telefones — regex) por placeholders `[[PII-1]]`, mantendo mapa local em `work/redaction_map.json` (nunca incluído no kit).
3. `atado kit --terms-only`: kit mínimo sem a transcrição completa — apenas `02_termos.md` (janelas de contexto) — para usuários que só querem resolver a tabela de siglas expondo o mínimo.
4. README: seção explícita sobre o que sai da máquina em cada modo.

## 8. Fases de execução (Claude Code)

**F6 — Protocolo e kit**: escrever `00_PROTOCOLO.md` (template Jinja2 em `src/atado/templates/`), implementar `atado kit` (+ `--compact`, `--terms-only`), `LEIA-ME.txt`. ✅ Aceite: kit gerado a partir das fixtures da F1 é legível, autocontido e ≤ limites de tamanho; revisão manual do protocolo contra as regras do §4 (checklist no PR).

**F7 — Loop de retorno**: `out/context.yaml`, `atado interview import` com parser tolerante + backup do `atado.yaml`, integração do `context.yaml` no próximo `kit`. ✅ Aceite: teste round-trip — saída sintética de agente → import → yaml atualizado → novo kit reflete o conhecimento.

**F8 — Redação/consentimento**: avisos, `--redact`, `redaction_map.json`. ✅ Aceite: fixtures com CPF/e-mail falsos são redigidas; mapa nunca aparece no kit.

**F9 — Providers API** (opcional, só após F6–F8 validados pelo usuário em uso real): base Protocol, adapter `anthropic` primeiro, sessão REPL com resume, depois `openai`/`gemini`/`ollama`. ✅ Aceite: sessão completa mockada em teste (provider fake); sessão real anthropic testada manualmente.

**F10 — Docs open source**: README atualizado com o fluxo completo (diagrama em texto: transcrever → kit → agente → import → iterar), guia "usando com Claude / ChatGPT / Gemini", exemplos de entrevista. ✅ Aceite: usuário novo consegue executar o fluxo Modo 1 só com o README.

## 9. Não-objetivos

- Autonomia total: o agente **não** decide sozinho o significado final de termos classe (c) — confirmação é do usuário.
- Orquestração multi-agente, RAG com vector store, fine-tuning.
- Armazenar chaves de API em arquivos do projeto.
- Resolver identidade real dos speakers automaticamente (o agente pode *perguntar* "quem é SPEAKER_01?" na entrevista — isso basta).

## 10. Decisões que o Claude Code NÃO deve mudar sem perguntar

1. Kit portátil (Modo 1) é o caminho primário; API é opcional e vem depois.
2. O protocolo (`00_PROTOCOLO.md`) é a única fonte do comportamento do agente — Modo 1 e Modo 2 usam o mesmo documento.
3. Regras da entrevista do §4-R3 (lotes de 3–4, hipóteses em vez de perguntas abertas, marcadores de confiança) são invioláveis.
4. Consentimento explícito antes de qualquer dado sair da máquina.
5. Sem LangChain/frameworks de agente; adapters finos sobre SDKs oficiais.

## 11. Riscos

- **Formato de saída do agente varia entre modelos** → sentinelas de bloco + parser tolerante + exemplos de formato dentro do próprio protocolo (few-shot).
- **Kit maior que a janela de contexto do agente do usuário** → `--compact` e `--terms-only`; documentar limites típicos por agente no LEIA-ME.
- **Alucinação em pesquisa** (agente "encontra" significado plausível mas errado) → o protocolo exige fonte citada + teste de compatibilidade com a transcrição + confirmação do usuário para virar `confirmada`.