# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/).

## [0.1.0] — 2026-07-15

Primeira versão funcional. Construída a partir de `specs/spec_a.md`, `specs/spec_b.md` e
das emendas validadas em `specs/spec_c_design_amendments.md`.

### Adicionado
- **Transcrição local** (WhisperX `large-v3`, `int8_float16`) com normalização via ffmpeg,
  cache/manifest determinístico e resiliência por arquivo.
- **Diarização** opcional (pyannote community-1) com atribuição de falante por sobreposição;
  falha amigável sem `HF_TOKEN`; `--no-diarize` sempre intacto.
- **Índice de termos** com ocorrências, janela de contexto e timestamps **local + global**
  (offset por arquivo, `source_start`), `terms.{md,csv}` e `suspects`.
- **Passe de correção de siglas** (rapidfuzz + casefold + sem-acento, limiar configurável).
- **Kit portátil** (`atado kit`) agent-agnóstico com `00_PROTOCOLO.md`, `--compact`,
  `--terms-only`, consentimento e `--redact` (PII).
- **Loop de retorno** (`atado interview import`): parser tolerante + escrita segura no
  `atado.yaml` (ruamel, backup, validação) + `context.yaml` + `narrative.md`.
- **Modo 2 (API)**: `atado reconstruct` com adapters anthropic/openai/gemini/ollama.
- 105 testes de unidade sobre o núcleo puro (sem GPU no CI).

### Notas
- Requer Python 3.10–3.12. Matriz de versões testada no README.
- Conteúdo de reunião e segredos nunca são versionados (`.gitignore`).
