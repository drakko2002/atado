# SPEC — `atado`: Transcritor local de reuniões fragmentadas (PT-BR)

> Documento de especificação para execução pelo Claude Code (Opus 4.8).
> Leia este documento inteiro antes de escrever qualquer código. Execute fase por fase, validando os critérios de aceite de cada fase antes de avançar.

---

## 1. Contexto e problema

O usuário possui **10–11 arquivos de áudio** de uma mesma reunião (Comitê Gestor de Dados / contexto institucional IFRS–UFSCar), em **português brasileiro claro e boa qualidade**, mas com **contexto fragmentado**: cada áudio cobre um trecho ("meias conversas"), com **múltiplos falantes**.

Objetivo final do usuário:
1. Transcrever tudo **localmente** (privacidade — conteúdo institucional não deve ir para APIs externas).
2. Identificar **quem fala** (diarização) para costurar contexto entre arquivos.
3. Consolidar as transcrições em um corpus único, ordenado e navegável por timestamps.
4. Gerar um **índice de termos/siglas** (ex.: CGD, CETEC, CESUA, PDI, PROSAS, FAE, ORSID, CIAP, SWAP, MEITUS, "Space") com todas as ocorrências + contexto ao redor, para preencher uma tabela de "Significado" de cada sigla.
5. Reduzir erros de transcrição de siglas/nomes próprios via `initial_prompt` com glossário + passe de correção.

O projeto será usado primeiro pelo autor e depois possivelmente publicado como **utilitário open source** (CLI).

## 2. Nome e identidade

- Nome do pacote/CLI: `atado` (de "ata" + particípio — "juntar as pontas"). Se o nome estiver ocupado no PyPI, usar `atado-cli`. Não publicar no PyPI nesta fase; apenas estruturar para isso.
- Licença: MIT.
- Idioma do código/identificadores: inglês. Idioma do README principal: português (com seção curta em inglês). Mensagens do CLI: português.

## 3. Stack técnica

| Componente | Escolha | Justificativa |
|---|---|---|
| Linguagem | Python ≥ 3.10, < 3.13 | compatibilidade com whisperx/pyannote |
| ASR | **WhisperX** (backend faster-whisper) | timestamps por palavra + diarização integrada |
| Modelo padrão | `large-v3` | melhor precisão em PT-BR |
| Diarização | pyannote.audio 3.x (via WhisperX) | requer token Hugging Face |
| Áudio | `ffmpeg` (conversão/normalização) | robustez de formatos (ogg/opus do WhatsApp, m4a, mp3, wav) |
| CLI | `typer` + `rich` | UX boa, progress bars |
| Config | `pydantic` + YAML (`pyyaml`) | validação do arquivo de projeto |
| Correção fuzzy | `rapidfuzz` | passe de correção de siglas |
| Empacotamento | `pyproject.toml` (hatchling ou setuptools), gerenciado com `uv` se disponível, senão `pip` | preparo para open source |
| Testes | `pytest` | unidade nas partes puras (merge, glossário, índice) |

**Detecção de hardware (obrigatório):**
- CUDA disponível → `device=cuda`, `compute_type=float16` (ou `int8_float16` se VRAM < 8GB).
- Apple Silicon → avisar que WhisperX/CTranslate2 roda em CPU no Mac; usar `compute_type=int8` e sugerir modelo `medium` se `large-v3` ficar lento.
- CPU puro → `compute_type=int8`, sugerir `medium` com aviso claro de tempo estimado.
- Flags `--device`, `--model`, `--compute-type` sempre sobrepõem a autodetecção.

**Nota sobre pyannote:** a diarização exige token HF (`HF_TOKEN` via env ou config) e aceite prévio das condições dos modelos `pyannote/speaker-diarization-3.1` e `pyannote/segmentation-3.0` no Hugging Face. O CLI deve detectar a ausência/erro de token e falhar com mensagem instrutiva (link das duas páginas de aceite), **sem stack trace cru**. Diarização deve ser **opcional** (`--no-diarize` continua funcionando sem token).

## 4. Modelo de projeto (workspace)

O usuário trabalha num diretório de projeto com esta estrutura, criada por `atado init`:

```
meu-projeto/
├── atado.yaml          # config do projeto
├── audios/             # usuário coloca os áudios aqui (qualquer formato)
├── work/               # intermediários (wav normalizados, json brutos) — gitignored
└── out/                # saídas finais
    ├── transcripts/    # 1 par .json + .md por áudio
    ├── consolidated.md # corpus unificado
    ├── consolidated.json
    ├── terms.md        # índice de termos (tabela)
    ├── terms.csv
    └── report.md       # relatório-resumo da execução
```

### 4.1 Schema do `atado.yaml`

```yaml
project: "Reunião CGD 2026-06"
language: pt
model: large-v3            # tiny|base|small|medium|large-v2|large-v3
diarize: true
min_speakers: null          # opcional
max_speakers: null          # opcional
order: name                 # name | mtime | manual
manual_order: []            # usado se order: manual — lista de nomes de arquivo

# Glossário: alimenta o initial_prompt e o passe de correção
glossary:
  context: >
    Reunião do Comitê Gestor de Dados (CGD), envolvendo IFRS e UFSCar.
  terms:
    - term: CGD
      meaning: "Comitê Gestor de Dados"
    - term: CETEC
      meaning: null            # desconhecido — só ajuda o ASR a grafar certo
      aliases: ["CETEQ", "SETEC"]   # erros prováveis a corrigir no pós-processo
    - term: PROSAS
      meaning: "Plataforma de gestão de projetos"
    # ...

# Termos a rastrear no índice mesmo que não estejam no glossário
track_extra: ["Space", "SWAP"]

output:
  context_window_seconds: 20   # janela de contexto ao redor de cada ocorrência no índice
```

Regras:
- `initial_prompt` é montado automaticamente: `glossary.context` + lista de `terms` (ex.: `"...Siglas e nomes citados: CGD (Comitê Gestor de Dados), CETEC, CESUA, UFSCar, PDI, PROSAS, FAE, CIAP, SWAP."`). Limitar a ~200 tokens; se o glossário exceder, priorizar termos e truncar o contexto livre.
- `aliases` NÃO entram no prompt; servem só ao passe de correção fuzzy pós-transcrição.

## 5. Comandos do CLI

```
atado init [dir]                 # cria estrutura + atado.yaml comentado
atado check                      # valida ambiente: ffmpeg, torch/cuda, token HF, modelos
atado transcribe [--only FILE]   # normaliza + transcreve (+ diariza) todos os áudios novos
atado merge                      # consolida transcripts em consolidated.{md,json}
atado terms                      # gera índice de termos terms.{md,csv}
atado suspects                   # lista tokens suspeitos (prováveis siglas mal transcritas)
atado run                        # pipeline completo: transcribe → merge → terms → report
```

Comportamentos obrigatórios:
- **Idempotência/cache**: `transcribe` pula áudios já processados (hash do arquivo em `work/manifest.json`); `--force` reprocessa.
- **Resiliência**: falha em 1 áudio não aborta o lote; erro vai para o relatório.
- Progresso com `rich` (arquivo atual, etapa, tempo estimado).
- `atado check` testa cada dependência isoladamente e imprime ✅/❌ com instrução de correção — este comando é a primeira coisa que o usuário roda.

## 6. Pipeline de transcrição (detalhe)

Por arquivo de áudio:

1. **Normalização** (`ffmpeg`): converter para WAV mono 16 kHz em `work/`. Aceitar no mínimo: wav, mp3, m4a, ogg, opus, flac, e **extrair áudio de mp4/mkv** se o usuário jogar vídeo na pasta.
2. **ASR**: WhisperX com `language="pt"`, `initial_prompt` montado do glossário, VAD padrão do WhisperX, `word_timestamps` via alinhamento (modelo de alinhamento PT).
3. **Diarização** (se habilitada): atribuição de speaker por palavra/segmento. Speakers são rotulados `SPEAKER_00`, `SPEAKER_01`… **por arquivo** (não tentar unificar identidade de voz entre arquivos — fora de escopo v1; ver §10).
4. **Passe de correção de glossário** (pós-ASR, determinístico):
   - Para cada palavra transcrita em CAIXA-ALTA-provável ou que case fuzzy (rapidfuzz, `ratio ≥ 85` ajustável) com um `term` ou `alias` do glossário → substituir pela grafia canônica do `term`. Registrar cada substituição no relatório (`"CETEQ" → "CETEC" (3x)`).
   - Nunca substituir palavras comuns do português; aplicar apenas a tokens fora de um dicionário básico (usar heurística: token com maiúsculas internas, ou len ≤ 8 todo maiúsculo, ou ausente de wordlist PT embutida pequena).
5. **Saídas por arquivo** em `out/transcripts/`:
   - `NOME.json`: segmentos com `{start, end, speaker, text, words[]}` + metadados (modelo, duração, data, versão do atado).
   - `NOME.md`: legível, formato:
     ```
     ## audio_03.ogg (duração 12:34)
     [00:08:03] SPEAKER_01: ... a nossa secretaria, a CETEC, vai encaminhar ...
     ```

## 7. Consolidação (`merge`)

- Ordenar arquivos conforme `order` do config (padrão: nome do arquivo, ordenação natural — `audio_2` antes de `audio_10`).
- `consolidated.md`: cabeçalho com sumário (nº de áudios, duração total, nº de speakers por arquivo), depois todos os transcripts em sequência, com âncoras por arquivo e timestamps **locais ao arquivo** (formato `arquivo @ mm:ss` — não inventar uma linha do tempo global, pois os áudios podem ter buracos entre si).
- `consolidated.json`: mesma estrutura, machine-readable — este é o arquivo que o usuário vai colar/anexar numa conversa com IA para reconstruir contexto, então deve ser **compacto** (sem `words[]`, só segmentos).

## 8. Índice de termos (`terms`) — coração do caso de uso

Para cada termo do glossário + `track_extra`:
- Encontrar todas as ocorrências (case-insensitive, incluindo formas corrigidas).
- Para cada ocorrência: arquivo, timestamp, speaker, e **janela de contexto** (`context_window_seconds` antes/depois, texto dos segmentos vizinhos).
- `terms.md`: uma seção por termo:
  ```
  ## CETEC — 4 ocorrências
  significado (config): (desconhecido)

  - audio_01 @ 08:03 — SPEAKER_01: "...então a nossa secretaria, a CETEC, fica responsável..."
  - audio_01 @ 08:14 — ...
  ```
- `terms.csv`: colunas `term,meaning,file,timestamp,speaker,context` (uma linha por ocorrência) — formato pronto para o usuário cruzar com a tabela de siglas que ele já mantém.

### 8.1 `atado suspects`

Varre os transcripts e lista candidatos a siglas/nomes próprios mal transcritos que **não** estão no glossário: tokens todo-maiúsculos, tokens com padrão de sigla, e palavras fora da wordlist PT com ≥ 2 ocorrências. Saída ordenada por frequência, com 1 exemplo de contexto cada. Objetivo: alimentar o loop de 2 passadas — usuário roda, revisa suspeitos, atualiza `glossary`, roda `atado transcribe --force` de novo.

## 9. Relatório (`report.md`)

Gerado ao fim de `atado run`: parâmetros usados, hardware detectado, tempo por arquivo, substituições do passe de correção, arquivos com erro, e "próximos passos" sugeridos (ex.: "3 termos suspeitos encontrados — rode `atado suspects`").

## 10. Não-objetivos (v1)

- Identificar o **mesmo falante entre arquivos diferentes** (re-identificação de voz global) — fora de escopo; documentar como ideia futura no README.
- Resumo/ata automática por LLM — fora de escopo; o produto entrega o corpus para o usuário levar ao LLM de sua escolha.
- Interface gráfica, servidor, tempo real.
- Tradução.

## 11. Estrutura do repositório

```
atado/
├── pyproject.toml
├── README.md            # PT-BR: instalação, pré-requisitos (ffmpeg, HF token), quickstart, exemplos
├── LICENSE              # MIT
├── .gitignore
├── src/atado/
│   ├── __init__.py
│   ├── cli.py           # typer app
│   ├── config.py        # pydantic models + load/validate atado.yaml
│   ├── hardware.py      # autodetecção device/compute_type
│   ├── audio.py         # ffmpeg normalize/extract
│   ├── asr.py           # wrapper WhisperX (transcribe/align/diarize)
│   ├── glossary.py      # montagem do initial_prompt + passe de correção (PURO, testável)
│   ├── merge.py         # consolidação (PURO, testável)
│   ├── terms.py         # índice de termos + suspects (PURO, testável)
│   ├── report.py
│   └── wordlist_pt.txt  # wordlist PT pequena (~10k palavras frequentes) embutida
└── tests/
    ├── test_glossary.py
    ├── test_merge.py
    ├── test_terms.py
    └── fixtures/        # JSONs de transcript sintéticos (NÃO testar ASR real no CI)
```

Princípio de arquitetura: **tudo que não depende de GPU/modelos é função pura sobre estruturas de dados** (transcript JSON in → JSON/texto out), coberto por testes. O ASR é uma casca fina em `asr.py`, importada tardiamente (lazy import) para que `init`, `check`, `merge`, `terms` funcionem sem torch instalado/carregado.

## 12. Fases de execução (para o Claude Code)

Executar em ordem. Cada fase termina com os testes passando e um commit.

**F0 — Scaffold**: repo, pyproject, CLI esqueleto com todos os comandos registrados (stubs), config pydantic + `atado init` funcional gerando `atado.yaml` comentado. ✅ Aceite: `atado init && atado check` roda (check pode reportar ❌ nas deps pesadas).

**F1 — Núcleo puro**: `glossary.py`, `merge.py`, `terms.py` completos com testes sobre fixtures sintéticas (criar 3 fixtures JSON simulando 3 áudios com siglas, erros tipo "CETEQ", múltiplos speakers). ✅ Aceite: `pytest` verde; `atado merge` e `atado terms` funcionam a partir de JSONs colocados manualmente em `out/transcripts/`.

**F2 — Áudio + ASR**: `audio.py` (ffmpeg), `hardware.py`, `asr.py` com WhisperX, cache/manifest, `atado transcribe` ponta a ponta **sem** diarização. ✅ Aceite: transcrever um WAV curto gerado sinteticamente (TTS não disponível → gerar tom + aceitar transcript vazio; o teste real de ASR é manual do usuário). `atado check` valida ffmpeg/torch de verdade.

**F3 — Diarização**: integração pyannote via WhisperX, tratamento de token HF ausente com mensagem instrutiva, `--no-diarize`, `min/max_speakers`. ✅ Aceite: erro de token produz mensagem amigável; pipeline com `--no-diarize` intacto.

**F4 — Pipeline e relatório**: `atado run`, `report.md`, `atado suspects`, resiliência a falha por arquivo, ordenação natural. ✅ Aceite: `atado run` em pasta com 1 áudio + 2 fixtures produz todas as saídas do §4.

**F5 — Polimento open source**: README completo em PT-BR (com seção "English summary"), exemplos de `atado.yaml`, troubleshooting (VRAM, Mac, token HF), CHANGELOG, verificação de que `pip install -e .` + `atado --help` funcionam limpo em venv novo. ✅ Aceite: seguir o README do zero num venv limpo funciona até `atado check`.

## 13. Decisões que o Claude Code NÃO deve mudar sem perguntar

1. WhisperX como engine (não trocar por whisper puro ou API externa).
2. Diarização opcional, nunca obrigatória.
3. Timestamps locais por arquivo (sem linha do tempo global).
4. Passe de correção só toca tokens fora da wordlist PT (nunca palavras comuns).
5. Nada de rede em runtime além do download inicial de modelos (HF).

## 14. Riscos conhecidos

- Conflitos de versão torch × ctranslate2 × pyannote: fixar versões testadas no `pyproject.toml` com ranges conservadores e documentar a matriz testada no README.
- `large-v3` tem tendência levemente maior a alucinar em silêncio → VAD do WhisperX mitiga; mencionar `--model large-v2` como fallback no troubleshooting.
- Áudios de WhatsApp (opus) com metadados estranhos → sempre re-encodar via ffmpeg (nunca passar o arquivo original ao modelo).