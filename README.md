# atado

> **Transcritor local de reuniões fragmentadas (PT-BR)** com índice de termos/siglas e
> reconstrução de contexto por um agente de IA da sua escolha.

`atado` resolve o problema de ter vários áudios/recortes de uma mesma reunião — múltiplos
falantes, siglas institucionais mal transcritas, contexto espalhado. Ele transcreve
**100% local** (WhisperX + pyannote), diariza, monta um **índice de todas as ocorrências**
de cada sigla (com contexto e timestamps) e prepara um **kit portátil** para um agente de
IA reconstruir os significados e a narrativa — **sem** precisar de chave de API.

**Privacidade primeiro:** a transcrição nunca sai da máquina. Só o `atado kit` (com seu
consentimento explícito) prepara conteúdo para levar a um agente externo.

---

## Fluxo completo

```
   audios/  ──►  atado transcribe  ──►  transcripts/  ──►  atado merge/terms  ──►  índice
                    (WhisperX +                                                      de termos
                     pyannote,                                                          │
                     local)                                                            ▼
                                                                              atado kit  ──►  out/kit/
                                                                                                │
   atado.yaml  ◄── atado interview import  ◄── (resposta do agente)  ◄── Claude/ChatGPT/Gemini/local
   (glossário                                                                (segue 00_PROTOCOLO.md)
    melhorado) ──► (opcional) retranscreve com aliases ──► kit v2 ...  [loop iterativo]
```

## Instalação

Requisitos: **Python 3.10–3.12**, **ffmpeg**. Para transcrever, uma GPU NVIDIA (CUDA 12)
ajuda muito, mas CPU funciona (mais lento).

```bash
# 1) ambiente
uv venv --python 3.12 .venv && source .venv/bin/activate     # ou conda create -n atado python=3.12

# 2) caminho LEVE (init/check/merge/terms/kit/interview) — sem torch
pip install -e .

# 3) caminho de ASR (para transcrever) — wheels CUDA a partir do índice do PyTorch
pip install --index-url https://download.pytorch.org/whl/cu124 torch torchaudio
pip install -e ".[asr]"

# 4) (opcional) integração via API — Modo 2
pip install -e ".[providers]"

atado check      # valide o ambiente
```

Para **diarização**, defina `HF_TOKEN` (Hugging Face) no `.env` e aceite as licenças de
[`pyannote/speaker-diarization-3.1`](https://huggingface.co/pyannote/speaker-diarization-3.1)
e [`pyannote/segmentation-3.0`](https://huggingface.co/pyannote/segmentation-3.0).

### Matriz testada (2026-07-15, RTX 4060 8 GB)

| Componente | Versão | Nota |
|---|---|---|
| Python | 3.12 | whisperx/pyannote não suportam 3.13 |
| torch / torchaudio | 2.8.0 + cu128 | wheels CUDA 12 |
| ctranslate2 | 4.8.1 | **≥4.5** (cuDNN 9) — evita `libcudnn_ops_infer.so.8` |
| faster-whisper | 1.2.1 | |
| whisperx | 3.8.6 | |
| pyannote.audio | 4.0.7 | pipeline *community-1* |
| compute_type | `int8_float16` | padrão para large-v3 em cards ≤ ~12 GB |

## Quickstart

```bash
atado init meu-projeto && cd meu-projeto
cp /caminho/dos/audios/* audios/
$EDITOR atado.yaml          # preencha glossário e (se forem recortes) os offsets
atado check
atado run                  # transcribe → merge → terms → report
atado kit                  # prepara out/kit/ para levar ao seu agente de IA
# ...leve o kit ao Claude/ChatGPT/Gemini, salve a resposta em resposta.md...
atado interview import resposta.md    # fecha o loop: atualiza glossário + context.yaml
```

## Comandos

| Comando | O que faz |
|---|---|
| `atado init [dir]` | Cria estrutura + `atado.yaml` comentado |
| `atado check` | Valida ambiente (ffmpeg, Python, disco, torch/CUDA, VRAM, HF token) |
| `atado transcribe [--only F] [--force] [--no-diarize]` | Normaliza + transcreve (+ diariza) |
| `atado merge` | Consolida em `consolidated.{md,json}` |
| `atado terms` | Índice de termos em `terms.{md,csv}` |
| `atado suspects` | Lista siglas provavelmente mal transcritas |
| `atado run` | Pipeline completo + `report.md` |
| `atado kit [--compact] [--terms-only] [--redact] [--yes]` | Kit portátil para o agente |
| `atado interview import <arquivo.md>` | Importa a saída do agente (glossário + context.yaml) |
| `atado reconstruct --provider anthropic [--model ...]` | Sessão interativa via API (Modo 2) |

## `atado.yaml` (exemplo)

```yaml
project: "Reunião CGD 2026-06"
language: pt
model: large-v3
diarize: true
order: offset                 # name | mtime | manual | offset
files:
  "recorte_01.mp3":
    source_start: "08:00"     # posição do recorte na gravação-mãe → timestamps globais
glossary:
  context: >
    Reunião do Comitê Gestor de Dados (CGD), IFRS e UFSCar.
  terms:
    - term: CGD
      meaning: "Comitê Gestor de Dados"
    - term: SETEC
      meaning: null
      aliases: ["CETEC", "CETEQ"]     # erros prováveis → corrigidos no pós-processo
track_extra: ["SIAPE", "ORCID"]
output:
  context_window_seconds: 20
correction:
  enabled: true
  threshold: 80
```

## Arquivos longos (1–2h) e onde salvar

Reuniões reais são longas. Quando um áudio passa de `long_audio.chunk_length` (padrão 10 min),
o `atado` transcreve **por blocos**: corta em silêncios, transcreve cada bloco, mostra
**progresso + ETA**, e **retoma de onde parou** se o processo cair (marcadores por bloco em
`work/chunks/`). O resultado é um único transcript com timestamps corretos.

```yaml
output_dir: "~/transcricoes/cgd"   # salvar out/ fora do projeto (padrão: out/)
long_audio:
  chunk_length: 600                # segundos por bloco (10 min)
  chunk_overlap: 3
  silence_snap: 30                 # corta no silêncio mais próximo da fronteira
```

Diarização de arquivos longos roda numa passada única sobre o arquivo (é o passo mais pesado —
o `atado` avisa; use `--no-diarize` ou `--model medium` se faltar VRAM). Toda saída respeita
`--output-dir`/`output_dir`; segredos e o mapa de redação nunca vão para lá (ficam em `work/`).

## Usando o kit com cada agente

- **Claude (claude.ai)**: nova conversa → anexe todos os `.md` do `out/kit/` → "Siga o `00_PROTOCOLO.md`."
- **ChatGPT / Gemini**: idem; anexe ou cole os arquivos em ordem; prefira modelos com contexto grande.
- **Local (Ollama)**: cole `00_PROTOCOLO.md` + `01`/`02`(+`03`). Sem busca, o agente pede queries
  (`PESQUISAR:`) para você pesquisar e colar de volta.

Kit grande demais? Use `atado kit --compact` (remove falas curtas de baixa informação,
preservando ocorrências de termos) ou `--terms-only` (só o índice de termos).

## Privacidade — o que sai da máquina

| Modo | O que sai |
|---|---|
| `transcribe`/`merge`/`terms`/`suspects` | **Nada** (100% local) |
| `kit` | O conteúdo do kit, **quando você o envia** a um agente (exige consentimento) |
| `kit --redact` | Idem, com PII (e-mail/CPF/telefone) mascarada; mapa fica em `work/` (fora do kit) |
| `kit --terms-only` | Só o índice de termos (exposição mínima) |
| `reconstruct` | A conversa vai à API do provedor escolhido |

Nomes de participantes ficam como `SPEAKER_xx`; a redação por regex é **best-effort**
(números falados por extenso podem escapar). Tokens/segredos sempre via `.env`, nunca no repo.

**Princípio:** a transcrição é sua. O `atado` é local-first e o autor do projeto **não tem —
e não pretende ter — acesso a nenhuma transcrição feita por usuários.**

### Diarização e LGPD

A diarização (identificação de "quem fala") processa características da **voz**, que é **dado
pessoal** (podendo ser sensível/biométrico conforme o uso) sob a **LGPD (Lei 13.709/2018)**.
Ao habilitar `diarize`:

- Você declara ter **base legal** para gravar e tratar esses dados (consentimento dos
  participantes ou outra hipótese dos arts. 7º/11) e ser o **responsável pelo tratamento**.
- O `atado` rotula falantes como `SPEAKER_00`, `SPEAKER_01`… e **não os identifica**; associar
  nomes reais é decisão sua e amplia suas obrigações de proteção.
- O processamento é **100% local** — nada é enviado a terceiros nesta etapa.
- **Minimização**: use `--no-diarize` se não precisar de falantes.

O `atado transcribe` exibe esse aviso por escrito quando a diarização está ligada. *Isto não é
aconselhamento jurídico.*

Para diarização, é preciso aceitar **três** licenças gated na sua conta HF (o pyannote 4.x usa a
pipeline *community-1*): [speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1),
[speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) e
[segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0); e usar um `HF_TOKEN` com
leitura de repositórios *gated*.

### Governança de segredos (chaves não vazam)

- **`HF_TOKEN` e chaves de provedores ficam só no `.env`** (gitignored) — nunca no `atado.yaml`
  nem no repositório.
- `atado check` **detecta** um valor tipo-token no `atado.yaml` e manda movê-lo para o `.env`.
- Saídas e mensagens de erro passam por um **mascarador** (`[[..._REDACTED]]`) — nenhum segredo
  vaza para `report.md`, logs ou stack traces.
- `scripts/scan_secrets.sh` varre os arquivos rastreados; roda na **CI** e como **git hook**:
  ```bash
  git config core.hooksPath .githooks   # ativa o pre-commit que bloqueia segredos
  ```

## Troubleshooting

- **`libcudnn_ops_infer.so.8` não encontrado** → use `ctranslate2>=4.5` (matriz do atado, cuDNN 9).
- **CUDA out of memory** (large-v3 em 8 GB) → `--compute-type int8` e/ou `--model medium`.
- **`torchcodec`/ffmpeg warning** → benigno para transcrição; o WhisperX decodifica via ffmpeg.
- **Python 3.13** → crie um ambiente 3.10–3.12 (whisperx/pyannote não têm wheels p/ 3.13).
- **Diarização falha** → confira `HF_TOKEN` e o aceite das licenças pyannote.
- **Disco cheio** → o `check` avisa; o stack de GPU ocupa ~6–10 GB.

## Não-objetivos (v1) e futuro

Fora de escopo agora: re-identificação de voz entre arquivos, ata automática por LLM,
GUI/servidor/tempo-real, tradução. **Direção futura** (registrada em `specs/`): ingestão de
reuniões de plataformas (Zoom/Meet/Teams) via API de gravação em nuvem + OAuth, sempre com
consentimento explícito.

## English summary

`atado` is a **local-first** CLI that transcribes fragmented meeting audio (PT-BR) with
WhisperX + pyannote, builds an **index of every acronym/term occurrence** (with context and
timestamps), and produces a **portable kit** you take to any capable LLM (Claude, ChatGPT,
Gemini, or a local model) to reconstruct acronym meanings and a meeting narrative — no API
key required for the primary flow. Nothing leaves your machine until you explicitly generate
and share a kit. Optional API mode (`atado reconstruct`) drives the same protocol via a
provider SDK. MIT licensed.

## Licença

MIT — veja [LICENSE](LICENSE).
