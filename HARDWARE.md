# Requisitos de hardware

Medido com uma **reunião real de 2h29** (a 25ª Reunião CGD, 8936 s de áudio), transcrita com
`large-v3`. O `atado` **auto-configura** `compute_type` e `batch_size` conforme a VRAM, então
na prática você não precisa ajustar nada — mas aqui está o que esperar.

## Perfil medido — RTX 4060 8 GB (placa modesta)

Máquina de validação: Ryzen 5 5500 · 16 GB RAM · **RTX 4060 8 GB**.

| Métrica | Valor |
|---|---|
| Tempo p/ 2h29 de áudio | **8,6 min** (~17× tempo real) |
| Config auto-selecionada | `int8_float16` · `batch_size=4` |
| Pico de VRAM | 7,2 GB / 8 GB (88%) |
| Pico de RAM (sistema) | ~12,5 GB |
| Disco por reunião | ~350 MB (WAV 16k ~286 MB + transcript + blocos transitórios) |
| Acurácia de palavra | **83,8%** vs transcrição de referência (large-v3); confiança média 72% |

> Em 8 GB, `batch_size=8` **estoura a VRAM** em blocos longos (e o OOM envenena o contexto
> CUDA). O `atado` já desce para `batch_size=4` automaticamente nesse card.

## Requisitos por faixa

| Faixa | GPU / VRAM | RAM | Disco | Config automática |
|---|---|---|---|---|
| **Mínimo (GPU)** | NVIDIA ≥ 6–8 GB (CUDA 12) | 16 GB | ~10 GB (modelos) | `int8_float16`, batch 2–4 |
| **Mínimo (CPU)** | — (sem GPU) | 16 GB | ~6 GB | `int8`, batch 4 — **lento** (várias horas p/ 2h) |
| **Recomendado** | 12–16 GB | 32 GB | ~15 GB | `int8_float16`/`float16`, batch 8 |
| **Ideal (FAI-UFSCar)** | **RTX 5090 32 GB** | 64 GB | 20 GB | **`float16`, batch 16** — mais rápido e mais preciso |

**Downloads (uma vez):** `large-v3` ~3 GB · modelo de alinhamento PT ~1 GB · (diarização)
pyannote ~0,5 GB. Cache em `~/.cache/huggingface`.

## Projeção para a 5090 32 GB (máquina-alvo da FAI)

Sem restrição de VRAM, o `atado` seleciona **`float16` + `batch_size=16`**:
- **Precisão maior** que `int8_float16` (sem perda de quantização) — melhora o WER.
- **Mais rápido**: a 5090 é ~3–4× a 4060 → estimados **2–4 min** para uma reunião de 2h29.
- **Diarização** roda com folga; 64 GB de RAM eliminam qualquer pressão de memória.
- Para **precisão máxima estável**, dá para fixar no `atado.yaml`: `compute_type: float16`,
  `batch_size: 16` (o auto já faz isso), e usar `diarize: true`.

## Como validar a precisão sem assistir à reunião

`atado confidence` (ou `confidence.md` gerado no `run`) usa os scores de palavra para
sinalizar os **trechos de baixa confiança** — na reunião de 2h29 foram ~40 trechos curtos
(minutos de revisão, não 2,5 h). Revise só esses. Havendo uma transcrição "gold", o **WER**
dá o número objetivo de acurácia.

## Notas
- Chunking automático em blocos de 10 min para arquivos longos: memória limitada, **resumível**
  após crash, progresso + ETA.
- `atado check` reporta VRAM/disco/token e recomenda a config; flags/`atado.yaml` sobrepõem a
  autodetecção.
