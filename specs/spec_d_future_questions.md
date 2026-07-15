# SPEC D (rascunho) — perguntas de rumo e respostas para a próxima iteração

> Registro das questões levantadas pelo usuário (2026-07-15) + respostas fundamentadas,
> para montar uma SPEC futura realista. **Nada aqui é implementado agora.**

## Princípio inviolável (P0) — o autor nunca acessa transcrições de usuários
Declaração do usuário: *"não pretendo de forma alguma ter acesso a quaisquer transcrições
realizadas por usuários"* + *"apenas a pessoa que transcreveu terá acesso"*. Isto é um
**princípio de design e operacional**, não um detalhe. Consequências técnicas para QUALQUER
versão futura:
- **Local-first por padrão** (já é assim): a transcrição nasce e fica na máquina do usuário.
- Se um dia houver storage/processamento **remoto**, ele precisa ser **zero-knowledge**:
  conteúdo cifrado com chave do usuário (client-side), servidor guarda apenas blobs que o
  autor não consegue ler; retenção mínima e deleção verificável; **sem telemetria de conteúdo**.
- Isso **restringe arquiteturas**: não dá para "processar no servidor e guardar em claro".
  Opções compatíveis: (i) tudo local; (ii) processamento efêmero no servidor + descarte
  imediato + entrega cifrada; (iii) cifra client-side ponta a ponta.

## Q1 — Foco do produto
Transcrever reuniões da **FAI/UFSCar** e atender **público geral** (como neste 1º caso), com
saída **funcional e legível por humanos**. Impactos já endereçados nesta versão:
- `wordlist_pt.txt` expandida (gerada, license-safe) → `suspects` e correção ficam úteis.
- Índice de termos + timestamps local/global → transcrição navegável.
Emendas futuras sugeridas: perfis de saída ("ata legível" vs "JSON para IA"); pós-edição
leve (pontuação/parágrafos) opcional.

## Q2 — Como o usuário acessa a transcrição?

### (a) Rodou localmente
- **Batch (hoje)**: arquivos → `out/`. *Emenda simples*: `output_dir` configurável no
  `atado.yaml` para salvar em **local pré-definido pelo usuário** (fora do projeto).
- **Tempo real / escuta ativa (NOVO, futuro)** — transcrição incremental conforme a reunião
  avança, salvando localmente:
  - **Captura de áudio**: loopback do sistema (PipeWire/PulseAudio no Linux, WASAPI loopback
    no Windows, ScreenCaptureKit/BlackHole no Mac) e/ou microfone.
  - **ASR em streaming**: janelas deslizantes + VAD; emite segmento parcial e depois final
    (faster-whisper suporta; latência de alguns segundos).
  - **Diarização em streaming é difícil** (pyannote streaming é experimental) → degradar para
    "sem falantes" ao vivo e, opcionalmente, re-diarizar ao final.
  - **Saída**: append incremental em `out/live/<sessão>.md` (local escolhido pelo usuário);
    ao encerrar, roda o pipeline completo (merge/terms/kit).
  - **Consentimento**: capturar áudio de uma reunião = gravar → mesmo aviso LGPD + all-party
    consent. `atado listen` deveria exigir atestado.
  - Novo comando provável: `atado listen --output <dir>`.

### (b) Via API/navegador (hospedado) — EM ABERTO
- Entrega possível: **e-mail com link temporário assinado** ou **download no navegador**,
  sempre atrás de autenticação do usuário.
- Dado o P0, a entrega deve garantir "só o usuário acessa": link **expira**, download único,
  conteúdo **cifrado**. Recomendação: **começar 100% local**; só avaliar hospedado quando
  houver segurança para cumprir P0 (o próprio usuário disse que isso "fica em aberto").

## Q3 — Arquivos de 2 h (e além)
O pipeline atual já lida em batch (WhisperX segmenta por VAD, não carrega tudo em RAM), mas
para robustez em áudios longos, emendas recomendadas:
- **Tempo**: `large-v3 int8_float16` na RTX 4060 roda bem acima do tempo real → 2 h ≈ 10–30
  min. Em CPU, horas → sugerir `medium` ou GPU. Mostrar **ETA por chunk** (rich).
- **Memória/disco**: escrita **incremental** dos segmentos em disco (não acumular o
  transcript inteiro em memória). WAV 16k mono de 2 h ≈ 230 MB; modelos ~3–5 GB.
- **Resumabilidade**: **manifest por-chunk** (hoje é por-arquivo) → retomar após crash sem
  refazer as 2 h. Expor `--chunk-length` (ex.: 30 min).
- **Diarização de 2 h**: pesada; processar em blocos com watchdog de VRAM; permitir fallback
  CPU ou pular diarização em áudios muito longos com aviso.
- **Prompt-bleed**: em áudios longos o `initial_prompt` se dilui → menos problema que nos
  recortes de 10 s (onde observamos alucinação).
- **Kit/janela de contexto de IA**: 2 h geram corpus grande → `--compact`/`--terms-only` e
  particionamento do kit por tema/tempo.

## Q4 — Ingestão de plataformas (Zoom/Meet/Teams) — ver também spec_c §6.5
Reforço: caminho legítimo = **cloud-recording API + OAuth read-only** (host consentiu ao
gravar). Bot/captura-local exigem atestado de consentimento explícito. Tokens via env/secure
store. Isso conecta com o modo "escuta ativa" (Q2a) quando a reunião é ao vivo e local.

## Resumo de emendas candidatas para a SPEC D
1. `output_dir` configurável (salvar fora do projeto). *(pequena)*
2. Modo **`atado listen`** — escuta ativa/tempo real, salvando local. *(média/grande)*
3. Processamento **por-chunk** com escrita incremental + manifest por-chunk + ETA. *(média)*
4. Ingestão de plataforma via OAuth de gravação em nuvem. *(grande)*
5. (Só se P0 for garantível) camada hospedada zero-knowledge com entrega por e-mail/link. *(grande)*
