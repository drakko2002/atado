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

## Q5 — Escuta ativa: como o modelo "escuta" uma reunião privada, e escopo legal

### Como escuta (tecnicamente)
O `atado` roda **na máquina do usuário** e captura o **áudio do próprio sistema** — não "invade"
nada remoto. Duas fontes:
- **Saída do sistema (loopback)**: o que sai pelos alto-falantes (a fala dos outros na reunião).
  Linux: monitor do sink (PipeWire/PulseAudio). Windows: WASAPI loopback. macOS: ScreenCaptureKit
  ou dispositivo virtual (BlackHole).
- **Microfone**: a fala do próprio usuário.
Combinando as duas, cobre a reunião inteira. **Captura por aplicativo/aba** (só o áudio do
Google Meet, por ex.) é viável: PipeWire captura o stream de um app específico; Windows tem
Process Loopback; macOS ScreenCaptureKit filtra por app. Ou seja: sim, dá para escutar
**exatamente a guia/app pedido**, e o áudio **nunca sai da máquina**.

### Escopo legal (não é aconselhamento jurídico)
Mesmo local e open-source, gravar reunião = **tratar voz de terceiros** (dado pessoal, LGPD).
Pontos reais:
- **Consentimento/normas de gravação**: no Brasil, a jurisprudência (STF) admite a **gravação
  ambiental por um dos interlocutores**. O caso aqui é mais delicado: o usuário quer **não estar
  presente** e deixar o app escutando — é gravar uma reunião da qual ele **não participa
  ativamente**, captando a fala de outros que podem não saber do "ouvinte". Isso pesa mais.
- **ToS da plataforma**: Google Meet/Zoom têm regras próprias sobre gravação/bots; algumas
  proíbem gravadores de terceiros. Verificar antes.
- **Postura recomendada do produto** (o usuário é o *controlador* dos dados): (1) **atestado de
  consentimento** obrigatório antes de escutar ("declaro ter direito de gravar esta reunião");
  (2) exibir o **aviso LGPD** (já existe); (3) **não** burlar indicadores de gravação da
  plataforma; (4) manter tudo **local**, só o usuário acessa (P0). Para uso pessoal/interno e
  open-source com atestado, é um risco que o usuário assume conscientemente. Para versão
  comercial/hospedada, **consultar um advogado**.

## Q6 — Como validar a precisão sem assistir à reunião

Não há como ter 100% de certeza sem uma referência (ground truth), mas dá para **limitar e
direcionar** a conferência para minutos em vez de horas:

1. **Scores de confiança** (já disponíveis): o WhisperX dá `avg_logprob`/`no_speech_prob` por
   segmento e **score por palavra** no alinhamento. Sinalizar os segmentos de baixa confiança →
   o usuário revisa só esses (tipicamente ~5–10% do áudio), não a reunião toda. *(Feature
   candidata: `atado confidence` / seção no report com os trechos duvidosos + timestamp.)*
2. **Benchmark com referência (WER)**: quando existe um transcript "gold" (como a
   `transcricao-final.md` desta reunião), calcular o **WER (Word Error Rate)** dá um número
   objetivo de precisão. Serve para *calibrar* o modelo/config; para reuniões novas não há gold.
3. **Alvo nos pontos de erro**: siglas e nomes próprios são onde o ASR mais erra — o **índice de
   termos** + **`suspects`** já isolam exatamente esses tokens para conferência dirigida.
4. **Desacordo entre modelos** (opcional): transcrever com dois modelos/configs e marcar as
   regiões onde discordam — sobem como "revisar". Custa 2× de compute, mas não exige áudio.
5. **Loop com IA (SPEC B)**: o agente sinaliza termos/afirmações implausíveis para o usuário
   confirmar — reduz a revisão ao que é incerto.

**Resposta curta:** confiança-por-segmento + revisão dirigida aos trechos de baixa confiança e
às siglas/nomes reduz a verificação a poucos minutos; e, havendo referência, o WER dá o número.
Vou **medir o WER** desta reunião de 2h contra a `transcricao-final.md` como demonstração.

## Resumo de emendas candidatas para a SPEC D
1. `output_dir` configurável (salvar fora do projeto). *(pequena)*
2. Modo **`atado listen`** — escuta ativa/tempo real, salvando local. *(média/grande)*
3. Processamento **por-chunk** com escrita incremental + manifest por-chunk + ETA. *(média)*
4. Ingestão de plataforma via OAuth de gravação em nuvem. *(grande)*
5. (Só se P0 for garantível) camada hospedada zero-knowledge com entrega por e-mail/link. *(grande)*
