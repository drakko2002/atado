# atado

> Transcritor local de reuniões fragmentadas (PT-BR), com índice de termos/siglas e reconstrução de contexto por agente de IA.

**Privacidade primeiro:** a transcrição roda 100% local (WhisperX + pyannote). Nada sai da máquina até você explicitamente gerar um "kit" para levar a um agente de IA.

`atado` resolve o problema de ter vários áudios/recortes de uma mesma reunião, com múltiplos falantes e siglas institucionais mal transcritas: transcreve, diariza, monta um índice de todas as ocorrências de cada sigla (com contexto e timestamps), e prepara um pacote para um agente de IA reconstruir os significados e a narrativa da reunião.

> Documentação completa em construção (fase F5/F10). Veja `specs/` para a especificação.

## Instalação rápida (dev)

```bash
# Requer Python 3.10–3.12 e ffmpeg.
uv venv --python 3.12 .venv
uv pip install -e ".[dev]"            # caminho leve (sem torch)
# Para transcrever (GPU CUDA 12 / cuDNN 9):
uv pip install --index-url https://download.pytorch.org/whl/cu124 torch torchaudio
uv pip install -e ".[asr]"
atado check
```

## Comandos

```
atado init [dir]        # cria estrutura + atado.yaml comentado
atado check             # valida ambiente (ffmpeg, torch/cuda, token HF, disco, VRAM)
atado transcribe        # normaliza + transcreve (+ diariza) áudios novos
atado merge             # consolida transcripts
atado terms             # índice de termos/siglas
atado suspects          # lista siglas provavelmente mal transcritas
atado run               # pipeline completo
atado kit               # gera kit portátil para um agente de IA (SPEC B)
atado interview import   # importa a saída do agente de volta ao projeto
atado reconstruct        # sessão interativa via API de um provedor (opcional)
```

Licença: MIT.
