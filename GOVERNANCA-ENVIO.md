# Governança de envio — rodar o `atado` em outra máquina (ex.: PC da FAI, RTX 5090)

> Como transferir um projeto de transcrição para outra pessoa/máquina **sem violar o
> princípio P0** (só quem transcreve acessa a transcrição) **nem a LGPD**, reaproveitando
> tudo o que já foi produzido. Este documento é público-seguro: ele lista *nomes de
> arquivos e processo*, nunca conteúdo de reunião.

---

## 1. O que É enviado (3 blocos)

| Bloco | O que é | Como vai |
|---|---|---|
| **Código** | O `atado` em si | **Não se envia** — a pessoa clona o repositório público (`github.com/drakko2002/atado`). Código e wordlist genérica já estão lá. |
| **Pacote privado** (obrigatório) | `atado.yaml` do projeto (glossário com siglas/nomes internos) | **Cifrado** (ver §3). É pequeno (~5 KB). |
| **Pacote privado** (opcional) | `out/` do projeto — transcrições prontas (`transcripts/*.json`), `terms.csv`, `confidence.md`, `PRECISAO.md` — e/ou o áudio original, se a pessoa for re-transcrever lá | **Cifrado** (ver §3). Enviar transcrições evita re-transcrever; enviar o áudio permite re-rodar com mais precisão na máquina melhor. |

**Reaproveitamento:** os `transcripts/*.json` são portáveis — na máquina nova, basta
colocá-los em `out/transcripts/` que `atado merge`, `terms`, `confidence`, `suspects` e
`kit` funcionam **sem re-transcrever nada**. O cache (`work/manifest.json`) é por máquina
e não precisa ir.

## 2. O que NUNCA é enviado

- **`.env`** (token Hugging Face, chaves de API) — cada pessoa cria o **seu** token
  (gratuito) e aceita as licenças pyannote na própria conta. Segredo não viaja.
- **`work/`** inteiro — contém intermediários e, se houve redação, o
  `redaction_map.json` (mapa reverso de PII).
- Qualquer coisa por canal **não cifrado** (anexo de e-mail comum, link público de drive).

## 3. Como enviar (cifrado, com senha fora de banda)

Empacote e cifre com senha forte (AES-256); a **senha vai por outro canal** (ex.: arquivo
por e-mail, senha por ligação/WhatsApp — nunca os dois juntos):

```bash
# na máquina de origem, dentro do diretório do projeto:
tar czf projeto-fai.tar.gz atado.yaml out/            # (out/ é opcional; some o áudio se quiser)
7z a -p -mhe=on projeto-fai.7z projeto-fai.tar.gz     # pede senha; -mhe cifra até os nomes
rm projeto-fai.tar.gz
# alternativa com GPG (se ambos usam GPG): gpg -c projeto-fai.tar.gz
```

Drive institucional com acesso restrito à pessoa também serve — desde que o arquivo já vá
**cifrado** (a cifra protege contra acesso indevido no trânsito e no repouso).

## 4. Setup na máquina de destino (ex.: 5090 32 GB + i9 + 64 GB)

```bash
# 1) código
git clone https://github.com/drakko2002/atado && cd atado
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
uv pip install --index-url https://download.pytorch.org/whl/cu128 torch torchaudio   # Blackwell → cu128
uv pip install -e ".[asr]"

# 2) credenciais PRÓPRIAS (nunca as de outra pessoa)
cp .env.example .env       # colar o SEU token HF (huggingface.co/settings/tokens, tipo Read)
# aceitar as 3 licenças: pyannote/speaker-diarization-community-1, .../speaker-diarization-3.1,
#                        .../segmentation-3.0

# 3) projeto recebido
atado init meu-projeto && cd meu-projeto
7z x projeto-fai.7z && tar xzf projeto-fai.tar.gz     # atado.yaml (+ out/ se enviado)
atado check                                            # deve mostrar float16 + batch 16 na 5090

# 4a) se recebeu só o glossário + áudio:  atado run
# 4b) se recebeu as transcrições prontas: atado merge && atado terms && atado confidence
```

Na 5090 o `atado` auto-seleciona **`float16` + `batch_size=16`** (mais preciso e ~3–4×
mais rápido que a validação na 4060). Nada a configurar.

## 5. Responsabilidades de quem recebe (LGPD)

Ao receber conteúdo de reunião, a pessoa passa a ser **responsável pelo tratamento**:
- manter tudo **local** (o `atado` não envia nada; o kit de IA só sai com consentimento);
- não versionar conteúdo em repositório (o hook do repo bloqueia mídia/segredos, mas a
  regra vale para qualquer cópia);
- apagar o pacote cifrado dos e-mails/drives após importar;
- diarização = tratamento de voz → o aviso do `atado transcribe` se aplica a quem roda.

## 6. Checklist rápido (quem envia)

- [ ] Pacote contém `atado.yaml` (+ `out/` e/ou áudio, se for o caso) — **e nada de `.env`/`work/`**
- [ ] Cifrado (7z AES-256 ou GPG), senha por canal separado
- [ ] Destinatário sabe que precisa do próprio token HF + aceites pyannote
- [ ] Combinado o que fazer com o pacote após importar (apagar)
