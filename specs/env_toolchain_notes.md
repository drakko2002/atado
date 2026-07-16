# Notas de ambiente e toolchain — diagnóstico `pip`/`uv`/conda

> **Tipo:** nota operacional (não é uma feature spec). **Data:** 2026-07-15.
> **Objetivo:** registrar o estado do ambiente Python deste projeto, o que já foi
> investigado/resolvido, e o que **ainda precisa ser validado por segurança** antes de
> mexer em configuração global (`~/.zshrc`). Escrito para que o Claude Code retome sem
> repetir a investigação.

---

## 1. Contexto / situação

O ambiente de execução deste projeto (`whisperwind`) é uma **venv criada pelo `uv`**
(`uv 0.11.24`) que fica em:

```
/home/cesar/miniconda3/envs/whisperwind/.venv/
```

Detalhes confirmados (`.venv/pyvenv.cfg`):

- `home = /home/cesar/miniconda3/envs/spendflow-env/bin` → a venv **empresta o Python
  3.12.12 do env conda `spendflow-env`**, mas tem `site-packages` isolado
  (`include-system-site-packages = false`).
- Criada por `uv` → **venvs de `uv` não instalam `pip`** por design (o instalador é o `uv`).
- `.venv/bin/python` é symlink para `spendflow-env/bin/python3.12`.

**Ativação empilhada (stacked):** no shell atual há DOIS ambientes ativos ao mesmo tempo:

- **conda** `spendflow-env` (`CONDA_PREFIX`, `CONDA_SHLVL=2`: base → spendflow-env)
- **a venv** `whisperwind/.venv` (`VIRTUAL_ENV`), cujo `bin` é o **1º item do `PATH`** (vence)

---

## 2. Problemas já endereçados (resolvido / diagnosticado)

### 2.1 `hf` CLI — ✅ RESOLVIDO (já estava instalado e correto)
- Contexto: o usuário instalou o plugin `hf-cli@huggingface/skills` (comando nativo do
  Claude Code, `/plugin`) e pediu para verificar/instalar o `hf` CLI.
- Verificado: `hf` está em `/home/cesar/miniconda3/envs/whisperwind/.venv/bin/hf`,
  **v0.36.2**, usando o `huggingface_hub` 0.36.2 da própria `.venv`. Interpretador do
  shebang bate com o `python` ativo. **Nada a instalar.**

### 2.2 `pip` aponta para o env ERRADO — ⚠️ DIAGNOSTICADO (correção pendente)
- Sintoma: `which python` → `.venv` (correto), mas `which pip` →
  `/home/cesar/miniconda3/envs/spendflow-env/bin/pip` (ERRADO). `python -m pip` falha
  (`No module named pip`, pois a venv de `uv` não tem `pip`).
- **Risco:** um `pip install <x>` "cru" instala silenciosamente no `spendflow-env`, não na
  `.venv` que o `python` realmente usa. Poluição do env errado.

---

## 3. Causa-raiz (confirmada)

Há **duas causas independentes** de o `spendflow-env/bin` estar no `PATH` (por isso ele
aparece **2×** no `PATH`):

1. **VSCode ativa o `spendflow-env`** (não é o shell rc!).
   - Evidência no env do shell: `TERM_PROGRAM=vscode`, `VSCODE_INJECTION=1`,
     `CONDA_SHLVL=2` com `CONDA_PREFIX_1=.../miniconda3` (base).
   - Ou seja: o rc ativa `base`; a extensão Python do VSCode injeta `conda activate
     spendflow-env` por cima; a `.venv` é sobreposta como interpretador selecionado.
   - Não há `.vscode/settings.json` na pasta do projeto → a seleção de interpretador vive
     no estado do VSCode (memória do workspace), não em arquivo versionado.

2. **`~/.zshrc` faz APPEND do `spendflow-env/bin` inteiro no `PATH`** (linhas ~45–50,
   bloco `>>> spendflow ops toolchain >>>`):
   ```zsh
   export PATH="$PATH:/home/cesar/miniconda3/envs/spendflow-env/bin"
   ```
   - **Intenção original** (comentário do próprio bloco): expor só `node/pnpm/npx` do
     `spendflow-env` para comandos de ops.
   - **Efeito colateral:** ao expor o diretório `bin` inteiro, também expõe `pip`, `pip3`,
     `python`, etc. → **este é o motivo que garante o vazamento do `pip` em QUALQUER shell**,
     independente do VSCode.

### O que foi DESCARTADO como causa
- **A outra sessão do VSCode rodando `spendflow-env` NÃO afeta este shell.** Variáveis de
  ambiente são **por-processo**; um terminal não injeta `CONDA_*`/`PATH` em outro. Pode
  deixar a outra sessão aberta sem problema.
- **Os arquivos rc NÃO auto-ativam `spendflow-env`.** O bloco `conda init` só ativa `base`
  (`auto_activate: True`, `default_activation_env: base`).

---

## 4. Regra de trabalho imediata (sem mexer em config)

> **NÃO use `pip` cru neste projeto. NÃO use `python -m pip` (a venv não tem `pip`).**
> Para instalar pacotes, use o `uv`, que respeita `VIRTUAL_ENV` automaticamente:

```bash
uv pip install <pacote>     # instala na .venv correta
```

Validado: `uv` está em `/usr/bin/uv` (v0.11.24) e um `--dry-run` resolveu para a `.venv`
correta ("Would make no changes" para `huggingface_hub`, já satisfeito lá).

---

## 5. Pendências — precisam de decisão/validação antes de prosseguir

### 5.1 Corrigir o vazamento do `pip` na raiz — ⏳ AGUARDANDO OK DO USUÁRIO
Opções apresentadas:

| # | Correção | Efeito | Trade-off |
|---|----------|--------|-----------|
| **A** | Não mexer em nada; usar sempre `uv pip install` | Instala sempre na `.venv` certa | Vazamento continua para quem digitar `pip` cru |
| **B** | **Estreitar o append do `~/.zshrc`**: expor só `node`/`pnpm`/`npx` (via um dir de symlinks) em vez do `spendflow-env/bin` inteiro | Elimina o vazamento do `pip` **e** mantém as ferramentas de ops | Edição única no `~/.zshrc` |
| **C** | Impedir o VSCode de ativar `spendflow-env` (interpretador lembrado / `python.terminal.activateEnvironment`) | Limpa o conda empilhado (cosmético) | Sozinho **não** corrige o vazamento (ainda precisa de B); chato de ajustar |

**Recomendação:** **B + hábito de A**. B remove o footgun na raiz sem quebrar o toolchain
de ops do `spendflow-env`; `uv pip` é o fluxo correto para uma venv `uv` de qualquer forma.

### 5.2 ⚠️ Validações de SEGURANÇA antes de editar o `~/.zshrc` (opção B)
Editar `~/.zshrc` é **config global do usuário** (afeta todos os shells e o toolchain de
ops do spendflow). Antes de aplicar B, **confirmar com o usuário** e validar:

- [ ] **Confirmar explicitamente** que pode editar `~/.zshrc` (não fazer sem OK).
- [ ] **Backup** do `~/.zshrc` antes de qualquer alteração (ex.: `cp ~/.zshrc ~/.zshrc.bak-2026-07-15`).
- [ ] Descobrir **exatamente quais binários de ops** são necessários no `PATH` (o comentário
      cita `node`, `pnpm`, `npx`; a Supabase CLI é via `npx supabase`, sem binário próprio).
      Verificar se há outros (ex.: `corepack`, `tsx`) antes de estreitar.
- [ ] Escolher **onde** ficam os symlinks estreitos (ex.: um dir dedicado tipo
      `~/.local/spendflow-ops-bin/` com symlinks só para os binários necessários) e apontar o
      append para esse dir — nunca para o `bin` inteiro.
- [ ] Garantir que o append estreito **não** re-exponha `pip`/`python` do `spendflow-env`.
- [ ] **Testar em shell novo** após a edição: `which pip` deve falhar (ou não achar o do
      spendflow), `node/pnpm/npx` devem continuar resolvendo, e `python`/`hf` devem continuar
      vindo da `.venv`.
- [ ] Reversão trivial documentada (restaurar o `.bak`).

### 5.3 Opção C (VSCode) — opcional, não bloqueante
- Ajustar a seleção de interpretador do workspace whisperwind para a `.venv` e/ou desligar a
  ativação automática de env no terminal, se o conda empilhado incomodar. **Não corrige o
  vazamento sozinho.** Baixa prioridade.

---

## 6. Referência rápida (fatos confirmados no shell atual)

```
which python  → /home/cesar/miniconda3/envs/whisperwind/.venv/bin/python   (correto)
which hf      → /home/cesar/miniconda3/envs/whisperwind/.venv/bin/hf        (correto, v0.36.2)
which pip     → /home/cesar/miniconda3/envs/spendflow-env/bin/pip           (ERRADO — vazamento)
uv            → /usr/bin/uv  (v0.11.24)
VIRTUAL_ENV   = .../whisperwind/.venv
CONDA_PREFIX  = .../spendflow-env   (CONDA_SHLVL=2: base → spendflow-env, via VSCode)
PATH          → spendflow-env/bin aparece 2× (VSCode + append do ~/.zshrc)
```

**Ação segura por padrão até decidir 5.1/5.2:** usar `uv pip install <pkg>` para tudo.
