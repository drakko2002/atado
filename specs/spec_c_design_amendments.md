# SPEC C — Design consolidado e emendas validadas (`atado`)

> Documento de design que **fecha** as SPEC A e SPEC B para implementação, incorporando o relatório de validação multiagente (2026-07-15) e as 4 decisões do usuário.
> Base: `spec_a.md` (F0–F5) + `spec_b.md` (F6–F10). Este documento registra apenas o **delta** e o plano de execução. Onde este documento e as specs divergirem, **este vence**.

---

## 0. Decisões do usuário (2026-07-15)

1. **Escopo**: construir **F0–F10 completo**, incluindo F9 (adapters de API `anthropic`/`openai`/`gemini`/`ollama`).
2. **ASR do baseline**: **GPU `large-v3` `int8_float16` + diarização** (pyannote), usando o HF token do `.env`.
3. **Linha do tempo** (resolve o BLOQUEADOR): **offset por arquivo** (`source_start`) + emitir timestamps **local E global** reconstruído.
4. **Housekeeping**: `AI_02` deletado (16 GB liberados; código preservado em `github.com/drakko2002/projeto-geracao-imagem`).

---

## 1. Ambiente-alvo travado

| Item | Valor |
|---|---|
| Python | **3.12** (via `uv`, `.venv` no diretório do projeto) |
| torch / torchaudio | wheel **cu124** (empacota cuDNN 9) |
| ctranslate2 | **≥ 4.5** (cuDNN 9 / CUDA 12) — evita `libcudnn_ops_infer.so.8` |
| whisperx / faster-whisper / pyannote.audio | versões resolvidas e **travadas** após validação em `.venv` |
| GPU | RTX 4060 8 GB → **`int8_float16`** (nunca `float16` no `large-v3`) |
| ffmpeg | presente (n8.1.2) |
| HF_TOKEN | **somente via env** (lido do `.env`, gitignored, nunca no `atado.yaml` nem no repo) |
| Empacotamento | `pyproject.toml`; deps GPU num **extra opcional** `atado[asr]`; caminho leve (`init/check/merge/terms/kit`) instala sem torch |

A matriz exata de versões vai para o `pyproject.toml` e para uma tabela "matriz testada" no README, **validada em `.venv` antes do F2** (pré-gate de viabilidade).

---

## 2. Emendas às specs (o que muda em relação a spec_a/spec_b)

### E1 — Linha do tempo global (BLOQUEADOR → resolvido) — *emenda a SPEC A §7, §13.3; alinha SPEC B §4-R3*
- `atado.yaml` ganha, por arquivo, um **`source_start`** opcional (`"HH:MM:SS"` ou segundos), representando a posição do recorte na gravação-mãe.
- Saídas (`terms.{md,csv}`, `consolidated.md`) emitem **ambos**: `arquivo @ 08:03 (local 00:03)`. Quando não há offset, só o local, com aviso.
- Quando offsets existem, a **ordem padrão** de `merge` passa a ser por offset (tempo do encontro).
- `§13.3` (proibição de timeline global) fica **revogado** por decisão explícita do usuário.

### E2 — Passe de correção de siglas (corrige no-op no real) — *emenda a SPEC A §6.4*
- Fixar scorer: **`rapidfuzz.fuzz.ratio`**.
- **`casefold` + remoção de acentos** em ambos os operandos antes de pontuar (Whisper emite siglas em minúsculas/Título, não CAIXA-ALTA).
- Detecção **não** depende de CAIXA-ALTA: caminho normalizado por caixa + regex de sigla `^[A-Za-zÀ-ÿ]{2,8}$` com dígitos/pontos internos.
- Limiar recalibrado (**~80**, configurável) e **teste unitário** garantindo que todo alias listado cruza o limiar após normalização (ex.: `CETEQ`↔`CETEC`, `ceteq`↔`SETEC`).
- Toda substituição é **logada** e reversível; canonicalização é conservadora (as grafias do glossário são "suspeitas", mudam após `interview import`).

### E3 — Contrato do JSON de transcript (fonte única) — *emenda a SPEC A §6.5, §11*
- Modelo **pydantic** `TranscriptDoc { meta, segments[] }`, `TranscriptSegment { start, end, speaker?, text, words[]? }`, `Word { start, end, word, score? }`.
- `speaker` é **opcional** em todo o pipeline (suporta `--no-diarize`).
- Fixtures da F1 e a saída de `asr.py` **validam** contra esse modelo (teste de conformância que fixture + amostra real de ASR devem passar).

### E4 — Disciplina de import tardio (verificada) — *emenda a SPEC A §11, §13.5*
- Teste de aceite (roda no ambiente sem torch): `atado init/check/merge/terms/kit` **sucedem com torch/whisperx desinstalados** (asserção de "nenhum ImportError").

### E5 — Contrato do parser da SPEC B (impede drift) — *emenda a SPEC B §4-R4, §5*
- **UMA** sentinela canônica, definida em um único lugar normativo e reusada pelo protocolo (F6) e pelo parser (F7): headings `## TABELA_RESOLVIDA`, `## NARRATIVA`, `## PENDENCIAS` (nível/caixa exatos).
- Few-shot do protocolo é **gerado a partir da mesma constante** do parser.
- **Teste round-trip**: o próprio exemplo few-shot do protocolo alimenta `interview import` e volta idêntico.
- `TABELA_RESOLVIDA` ganha coluna **`Variantes/Aliases`** (o import mapeia para `glossary.terms[].aliases`), fechando a promessa de §5.
- **`NARRATIVA` é persistida** em `out/narrative.md` (deixa de ser descartada).

### E6 — Escrita segura no `atado.yaml` — *emenda a SPEC A §3, SPEC B §5, §7*
- Read-modify-write com **`ruamel.yaml`** (preserva comentários/ordem/estrutura do config comentado do `init`).
- `interview import` ingere saída de LLM **não-confiável**: `safe_load`/`safe_dump` sempre; **validação pydantic** de todo campo (limite de tamanho, rejeita `\n`/control chars/tags YAML); **backup** do anterior; escrita em arquivo temporário re-parseado antes de substituir.
- Teste F7 reforçado: comentários/estrutura **sobrevivem** ao round-trip.

### E7 — Wordlist PT (proveniência + normalização) — *emenda a SPEC A §6.4, §8.1, §11*
- Fonte com licença compatível com MIT (ou script de build); normalização `casefold`+acentos no lookup; documentar se são lemas ou formas de superfície; **filtro por frequência/stopwords** para não inundar suspects.
- `correction`/`suspects` recebem a wordlist como **argumento injetado** → testes usam fixture pequena e determinística.

### E8 — Privacidade sob um único portão — *emenda a SPEC A §7, SPEC B §7*
- `consolidated.json/.md` ganham cabeçalho de aviso (conteúdo não redigido; sai da máquina se compartilhado); o hand-off para IA é roteado **exclusivamente** pelo `atado kit` (consentimento + redação opcional).
- Redação: `--redact`/`--terms-only` **first-class** também no `atado reconstruct` (mesma implementação); redação declarada **best-effort** (regex sobre fala tem falsos-negativos); **nomes de participantes** mantidos como `SPEAKER_xx` e não voltam para kits por padrão.
- `HF_TOKEN` **env-only**; `check` avisa se um valor tipo-token aparecer no `atado.yaml`.

### E9 — Realidade dos recortes de 10 s — *emenda a SPEC A §1, §6.3, §8, §10; SPEC B §4*
- `diarize` **auto-desliga com aviso** quando a duração mediana < ~30 s (diarização em 10 s é ruído e não costura entre arquivos). *No baseline o usuário pediu demo de diarização → habilitada explicitamente.*
- `context_window_seconds` é **limitado à duração do arquivo**, com nota em `report.md` quando a janela == arquivo inteiro.
- `TABELA_RESOLVIDA`/índice de termos é o **entregável primário**; `NARRATIVA` é **best-effort** e sinalizada como parcial quando a cobertura é esparsa (110 s de 11 recortes ≠ reconstrução de 2,5 h).
- `terms.md`/`report.md` declaram **cobertura** explícita ("índice reflete só os recortes fornecidos, não a gravação completa").

### E10 — Robustez de ambiente e cache — *emenda a SPEC A §5, §7, §14*
- `atado check`: preflights de **disco** (≥ ~15 GB p/ caminho GPU), **versão do Python** (falha clara se ≠ 3.10–3.12), **VRAM livre** com margem, **token HF** e **teste GPU mínimo** (transcrição de 1 s que dispara o erro cuDNN cedo, com correção instrutiva — sem stack trace cru).
- `manifest.json`: schema definido (sha256 do input, hash do WAV normalizado, modelo, língua, flag diarize, **hash do glossário/initial_prompt**, versão do atado, saídas, status, timestamp); **re-processa quando qualquer campo que afeta a transcrição muda**, não só com `--force`; escrita atômica.
- Ordenação `merge`: algoritmo de natural-sort especificado (trata `...36.mp3`, `...36(1).mp3`, `(2)`; mtimes idênticos ⇒ nunca rotular como cronológico); default para offset quando presente; fixtures com o padrão real de nome do WhatsApp.
- ASR atrás de **seam injetável** (callable/`Protocol`) → wiring de `asr.py` testado em CI com fake; transcrição real de WAV e `atado run` marcados como **gate manual/integração** (env 3.12 + GPU).

### E11 — F9 (providers) sem hard-code frágil — *emenda a SPEC B §6, F9*
- SDKs de provider num **extra opcional**; **sem** model-ids hard-coded nos defaults — lidos do config e validados contra o SDK no início da sessão; verificar o id/contrato de `web_search` da Anthropic no momento de construir F9.

---

## 3. Arquitetura (SPEC A §11 + ajustes)

```
atado/
├── pyproject.toml            # deps leves + extras: [asr], [providers]; matriz travada
├── README.md · LICENSE(MIT) · CHANGELOG.md · .gitignore (inclui .env, .venv, work/)
├── src/atado/
│   ├── cli.py                # typer; SEM import de torch no topo
│   ├── config.py             # pydantic + ruamel.yaml (load/validate/patch)
│   ├── models.py             # TranscriptDoc/Segment/Word (E3) — contrato único
│   ├── hardware.py           # device/compute_type (int8_float16 default)  [lazy torch]
│   ├── audio.py              # ffmpeg normalize/extract → WAV mono 16k
│   ├── asr.py                # casca fina WhisperX (transcribe/align/diarize) [lazy]
│   ├── glossary.py           # initial_prompt + passe de correção  (PURO)
│   ├── merge.py              # consolidação + offsets/timeline       (PURO)
│   ├── terms.py              # índice de termos + suspects           (PURO)
│   ├── redact.py             # PII best-effort (E8)                  (PURO)
│   ├── kit.py                # geração do kit + protocolo (Jinja2)   (PURO)
│   ├── interview.py          # parser tolerante + import (E5/E6)     (PURO)
│   ├── report.py             # montador puro + writer fino
│   ├── providers/            # base Protocol + anthropic/openai/gemini/ollama (F9)
│   ├── templates/            # 00_PROTOCOLO.md.j2, LEIA-ME.txt.j2, ...
│   └── wordlist_pt.txt
└── tests/  (glossary, merge, terms, interview round-trip, redact, kit, schema-conformance, lazy-import)
```

**Princípio (preservado)**: tudo que não é GPU é função pura sobre dados, coberto por testes. ASR é casca fina com import tardio.

---

## 4. Plano de fases (revisado, com pré-gates)

- **F0 Scaffold** — repo/pyproject (extras), CLI stub c/ todos os comandos, `config.py`+`init` gerando `atado.yaml` comentado (com `source_start`). ✔ `init && check` roda; check reporta ❌ nas deps pesadas.
- **F1 Núcleo puro** — `models.py`, `glossary`, `merge`(+offsets), `terms`, `redact`, wordlist; fixtures sintéticas (incl. erros "CETEQ", multi-speaker, nome estilo WhatsApp, arquivo oversized p/ `--compact`). ✔ `pytest` verde + **teste lazy-import** (sem torch).
- **PRÉ-GATE ASR** — validar matriz em `.venv`, travar pins, transcrição real de 1 clipe (dispara cuDNN cedo). *(em andamento em background)*
- **F2 Áudio+ASR** — `audio`, `hardware`, `asr` (seam injetável), manifest/cache. ✔ transcribe ponta a ponta **sem** diarização em 1 clipe real; `check` valida ffmpeg/torch de verdade.
- **F3 Diarização** — pyannote via WhisperX; token HF ausente/licença → mensagem instrutiva; `--no-diarize`, `min/max_speakers`. ✔ erro amigável; pipeline `--no-diarize` intacto.
- **F4 Pipeline+relatório** — `run`, `report.md`, `suspects` (persiste `out/suspects.md`), resiliência por arquivo, ordenação. ✔ `run --no-diarize` em 1 áudio + 2 fixtures produz todas as saídas.
- **F5 Polimento OSS** — README PT-BR (+English summary), matriz testada, troubleshooting (VRAM/cuDNN/token), `pip install -e .` limpo.
- **F6 Protocolo+kit** — `00_PROTOCOLO.md.j2` (regras §4-R1..R4 + sentinelas E5), `kit` (+`--compact`/`--terms-only`), `LEIA-ME`. ✔ kit das fixtures legível/autocontido; checklist do protocolo.
- **F7 Loop de retorno** — `context.yaml` (schema definido), `interview import` (E5/E6), reinjeção no próximo kit. ✔ round-trip sintético preserva comentários.
- **F8 Redação/consentimento** — avisos, `--redact`, `redaction_map.json` (0600, fora do kit). ✔ CPF/e-mail falsos redigidos; mapa nunca no kit.
- **F9 Providers API** — base Protocol, adapter `anthropic` primeiro, REPL c/ `--resume`, depois `openai`/`gemini`/`ollama`. ✔ sessão mockada em teste (provider fake).
- **F10 Docs** — fluxo completo, guia por agente, exemplos de entrevista.

---

## 5. Baseline (o "resultado base")

1. Transcrever os **10 clipes únicos** (11 arquivos, 1 par duplicado) com **`large-v3 int8_float16` + diarização** (HF token).
2. Gerar `consolidated`, **`terms`** (índice), `suspects`, e o **kit**.
3. **Eu (Opus)** executo o papel do agente reconstrutor (protocolo da SPEC B) sobre o resultado: pesquiso os termos (CETEC/SETEC, ORCID, DSpace, PROSAS, MEITUS, CIAP, CESUA, FAE, SWAP…), produzo `TABELA_RESOLVIDA` + `NARRATIVA` + `PENDENCIAS`.
4. **Benchmark**: comparar a transcrição do `atado` com `samples/context/transcricao-final.md` (referência large-v3+pyannote) — qualitativo + WER aproximado nos trechos correspondentes.

---

## 6. Decisões da SPEC A §13 preservadas (não mudam)
- WhisperX como engine (não trocar por whisper puro/API). ✔
- Diarização **opcional** (nunca obrigatória) — no baseline é ligada por escolha do usuário. ✔
- Passe de correção só toca tokens fora da wordlist PT. ✔
- Nada de rede em runtime além do download de modelos (HF) — e, na SPEC B, o hand-off consentido ao agente. ✔
- **Revogado por decisão do usuário**: §13.3 (timestamps só locais) → ver E1.
