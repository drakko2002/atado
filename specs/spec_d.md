# SPEC D — `atado`: arquivos longos, tempo real e além (roadmap + Fase D1)

> Guarda-chuva das próximas iterações. Pré-requisito: SPEC A/B (F0–F10) concluídas e
> publicadas. Este documento traça o roadmap D1–D4 e **detalha a Fase D1** (arquivos longos
> + `output_dir`). D2–D4 ficam esboçadas, para virarem specs próprias quando chegar a vez.
> Documento para execução pelo Claude Code (Opus 4.8). **Rascunho para revisão.**

---

## 1. Contexto e motivação

O baseline validou o núcleo com **recortes de 10 s**. Mas o caso de uso real — reuniões da
**FAI/UFSCar** e público geral — são **arquivos de 1–2 h**. Transcrever 2 h exige robustez
que o pipeline atual (feito para arquivos curtos) não garante: memória limitada,
**resumabilidade** após crash, e **progresso/ETA**. Além disso, o usuário quer salvar a saída
em **local escolhido por ele**, não dentro do projeto.

**Princípio P0 (inviolável, de spec_d_future_questions.md):** a transcrição é do usuário; o
autor do projeto **nunca acessa** transcrições de usuários. Tudo em D1 é **local-first**.

## 2. Roadmap (decomposição)

| Fase | Feature | Tamanho | Depende de | Status |
|---|---|---|---|---|
| **D1** | Arquivos longos (1–2 h): chunking, escrita incremental, manifest por-chunk (resumível), ETA + `output_dir` | médio | pipeline atual | **detalhada aqui** |
| **D2** | `atado listen` — escuta ativa/tempo real (captura de áudio do sistema + ASR streaming) | médio/grande | D1 (chunking) | esboço §4 |
| **D3** | Ingestão de plataformas (Zoom/Meet/Teams) via OAuth de gravação em nuvem | grande | — | esboço §4 |
| **D4** | Camada hospedada zero-knowledge (entrega por e-mail/link) | grande | D1–D3 + P0 garantível | esboço §4 |

Cada fase posterior vira sua própria spec (design → plano → implementação).

---

## 3. Fase D1 — arquivos longos + `output_dir` [DETALHADA]

### 3.1 Objetivos
1. Transcrever arquivos de 1–2 h (e além) com **memória limitada** e **sem perder trabalho**
   se o processo cair no meio.
2. Mostrar **progresso e ETA** por bloco.
3. Salvar saídas em **`output_dir`** definido pelo usuário (padrão: `out/` do projeto).
4. Manter timestamps corretos: **`chunk_offset` (dentro do arquivo) + `source_start` (arquivo
   no encontro)** → tempo global, coerente com E1.

### 3.2 Design técnico

**Chunking (o coração da D1):**
- Dividir o WAV normalizado em janelas de `chunk_length` (padrão **600 s = 10 min**), cortando
  em **fronteiras de silêncio** próximas do alvo (via `ffmpeg silencedetect`) para não partir
  palavras; se não houver silêncio na janela de tolerância, corta no tempo fixo com **overlap**
  (`chunk_overlap`, padrão 3 s).
- Cada chunk é um WAV em `work/chunks/<arquivo>/<idx>.wav` com um `chunk_offset` conhecido.
- Cada chunk é transcrito pelo `whisperx_transcribe` **já existente** (seam injetável mantido);
  os timestamps locais do chunk recebem `+chunk_offset` para virar tempo local-do-arquivo.

**Merge de chunks → TranscriptDoc do arquivo:**
- Concatena os segmentos dos chunks em ordem; na **região de overlap** entre o chunk N e N+1,
  descarta os segmentos duplicados do chunk N+1 (mantém os do N), com dedup por similaridade de
  texto+tempo. Função **pura/testável** (`merge_chunks(chunk_docs, offsets, overlap)`).

**Resumabilidade (manifest por-chunk):**
- Estender o manifest: além de `(arquivo → status)`, gravar `(arquivo, chunk_idx) → {input_hash
  do chunk, signature, status}`. `atado transcribe` pula chunks já `ok`; um crash em 1h50
  retoma do último chunk incompleto, não do zero. Escrita atômica por chunk.

**Escrita incremental (memória limitada):**
- Cada chunk transcrito é persistido em disco (`work/chunks/.../<idx>.json`) assim que pronto;
  o `TranscriptDoc` final do arquivo é **assemblado a partir do disco**, não acumulado inteiro
  em RAM durante a corrida. (2 h ≈ dezenas de milhares de segmentos — cabe em memória, mas a
  escrita incremental garante que nada se perde e permite arquivos ainda maiores.)

**Progresso/ETA:**
- `rich.progress` com barra por chunk; ETA = `elapsed/chunks_done × chunks_restantes`. Loga o
  chunk atual e o tempo por chunk (útil para estimar CPU vs GPU).

**Diarização de arquivos longos:**
- Padrão: diarizar o **arquivo inteiro** em uma passada (pyannote lida com áudio longo, mas é
  o passo mais pesado — VRAM/tempo). Manter a degradação graciosa já existente. `--no-diarize`
  intacto. *(Diarização por-chunk com casamento de embeddings entre chunks fica para D2/futuro:
  ao vivo é onde ela importa.)* Aviso quando a duração for grande e a VRAM apertada.

**`output_dir`:**
- Novo campo em `atado.yaml` (`output_dir: null` → usa `out/` do projeto) e flag `--output-dir`.
  Aceita caminho absoluto ou relativo; resolvido em `workspace.py`. Todas as saídas
  (transcripts, consolidated, terms, kit, report) passam a respeitá-lo. **Segredos/PII continuam
  fora do `output_dir`** (o `redaction_map.json` permanece em `work/`).

### 3.3 Adições de schema (`atado.yaml`)
```yaml
output_dir: null          # caminho onde salvar out/ (null = out/ do projeto)
long_audio:
  chunk_length: 600       # segundos por bloco (padrão 10 min)
  chunk_overlap: 3        # segundos de sobreposição entre blocos
  silence_snap: 30        # janela (s) p/ buscar silêncio perto da fronteira
```
Regra: chunking só é acionado quando a duração do arquivo > `chunk_length` (arquivos curtos
seguem o caminho atual, sem overhead).

### 3.4 Módulos afetados
- `audio.py`: `probe_silences()` (ffmpeg silencedetect) e `split_into_chunks()` → lista de
  `(wav_path, chunk_offset)`.
- `merge.py` (ou novo `chunks.py`): `merge_chunks()` puro (concat + dedup de overlap).
- `manifest.py`: entradas por-chunk + `needs_processing_chunk()`.
- `pipeline.py`: `transcribe_long_file()` (loop de chunks) escolhido quando `dur > chunk_length`.
- `config.py`: `output_dir`, `long_audio.*`.
- `workspace.py`: resolução de `output_dir` (todas as saídas passam por ele).

### 3.5 Fases de execução (para o Claude Code)
- **D1.0 — `output_dir`** *(pequena)*: config + resolução no workspace + todas as saídas
  respeitam. ✅ Aceite: `output_dir` aponta para `/tmp/xyz` e as saídas vão para lá.
- **D1.1 — chunking puro** *(TDD)*: `split_into_chunks` + `merge_chunks` (dedup de overlap),
  fixtures sintéticas. ✅ Aceite: `pytest` verde; um doc reconstruído de N chunks == o doc de
  referência (sem duplicatas na fronteira; timestamps com `chunk_offset` corretos).
- **D1.2 — transcribe por-chunk + resume**: `transcribe_long_file` com manifest por-chunk,
  escrita incremental, seam injetável. ✅ Aceite: matar o processo no meio e retomar transcreve
  só os chunks faltantes (verificável com transcritor fake que conta chunks).
- **D1.3 — progresso/ETA**: barra rich + ETA por chunk.
- **D1.4 — diarização longa + docs**: passada única no arquivo, avisos de VRAM; README/CHANGELOG.
  ✅ Aceite: transcrever um WAV real de ~30 min ponta a ponta (gate manual/GPU).

### 3.6 Aceite geral de D1
- Um arquivo sintético/real de **≥ 30 min** transcreve com memória estável, é **resumível**
  (crash no meio → retoma), mostra ETA, e a saída vai para o `output_dir`. Testes puros cobrem
  chunking/merge/dedup e o resume (com transcritor fake).

### 3.7 Não-objetivos de D1
- Tempo real / escuta ativa (D2). Ingestão de plataformas (D3). Camada hospedada (D4).
- Diarização por-chunk com re-identificação entre chunks (fica para quando D2 exigir streaming).

### 3.8 Riscos de D1
- **Cortar palavras na fronteira** → `silencedetect` + overlap + dedup testado.
- **Dedup de overlap errado** (perder ou duplicar fala) → função pura com fixtures de fronteira.
- **Diarização de 2 h estoura VRAM** → passada única com watchdog; permitir `--no-diarize` ou
  `medium`; documentar footprint.
- **`output_dir` em local sem permissão / disco cheio** → validar no início, erro claro.
- **Deriva de timestamps** com dois offsets (chunk + source_start) → teste explícito da soma.

---

## 4. Esboço de D2–D4 (viram specs próprias)

### D2 — `atado listen` (escuta ativa / tempo real)
- **Captura de áudio do sistema**: PipeWire/PulseAudio (Linux), WASAPI loopback (Windows),
  ScreenCaptureKit/BlackHole (Mac) e/ou microfone. Camada `sources/audio_capture/` por SO.
- **ASR streaming**: buffer deslizante + VAD; emite segmento **parcial** e depois **final**
  (faster-whisper suporta; latência de alguns segundos). Reusa os chunks da D1 como unidade.
- **Saída ao vivo**: append incremental em `output_dir/live/<sessão>.md`; ao encerrar, roda o
  pipeline completo (merge/terms/kit).
- **Diarização ao vivo**: difícil → rótulo genérico ao vivo, re-diarizar ao final (opcional).
- **Consentimento**: capturar = gravar → aviso LGPD + atestado all-party obrigatório.
- Comando: `atado listen --output <dir>`.
- Riscos: SO-específico, latência, diarização streaming, consentimento.

### D3 — Ingestão de plataformas (OAuth de gravação em nuvem)
- Caminho legítimo: **cloud-recording API read-only** — Zoom `recording:read`, Google Meet/
  Drive, MS Graph `OnlineMeetingRecording.Read`. Módulo `sources/<provider>.py` → baixa a
  gravação para `audios/` → fluxo atual. Bot/captura exigem atestado de consentimento.
- Tokens OAuth via env/secure store, nunca no `atado.yaml`.
- `atado ingest zoom --meeting <id>`.
- Riscos: ToS das plataformas, consentimento de todas as partes, expiração/refresh de token.

### D4 — Camada hospedada zero-knowledge
- Só se o **P0** (autor sem acesso) for garantível: cifra **client-side**, servidor guarda
  apenas blobs ilegíveis pelo autor; retenção mínima + deleção verificável; sem telemetria de
  conteúdo. Entrega por e-mail/link temporário assinado, atrás de autenticação do usuário.
- Recomendação: só avaliar depois de D1–D3 sólidas e com garantias de segurança para o P0.

---

## 5. Decisões que o Claude Code NÃO deve mudar sem perguntar
1. **P0**: local-first; o autor nunca acessa transcrições de usuários. Nenhuma feature de D1
   envia dados para fora.
2. Consentimento explícito antes de qualquer dado sair da máquina (herdado da SPEC B).
3. Timestamps em dois níveis: `chunk_offset` (dentro do arquivo) + `source_start` (arquivo no
   encontro) → tempo global. Não inventar uma terceira convenção.
4. Chunking só quando `duração > chunk_length`; arquivos curtos seguem o caminho atual.
5. Segredos/PII (token, `redaction_map.json`) nunca vão para `output_dir`.
