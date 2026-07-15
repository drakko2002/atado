#!/usr/bin/env bash
# Guardrail: falha se algum segredo (HF/provider/GitHub) aparecer em arquivos rastreados.
# Uso: scripts/scan_secrets.sh [arquivos...]  (sem args = todos os arquivos rastreados)
# NÃO imprime o valor do segredo, só o local.
set -uo pipefail

PATTERNS='hf_[A-Za-z0-9]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{20,}'
# arquivos que contêm PADRÕES/exemplos por design (não são segredos reais):
EXCLUDE='^(src/atado/security\.py|tests/test_security\.py|scripts/scan_secrets\.sh|\.githooks/pre-commit|\.github/workflows/)'

if [ "$#" -gt 0 ]; then
  mapfile -t FILES < <(printf '%s\n' "$@")
else
  mapfile -t FILES < <(git ls-files)
fi

hits=0
for f in "${FILES[@]}"; do
  [[ "$f" =~ $EXCLUDE ]] && continue
  [ -f "$f" ] || continue
  if grep -EqI "$PATTERNS" "$f" 2>/dev/null; then
    lines=$(grep -EnI "$PATTERNS" "$f" 2>/dev/null | cut -d: -f1 | paste -sd, -)
    echo "❌ possível segredo em: $f (linha(s): $lines)"
    hits=1
  fi
done

if [ "$hits" -eq 0 ]; then
  echo "✓ nenhum segredo detectado"
  exit 0
fi
echo "Remova o segredo (use .env, nunca versione) antes de commitar/publicar."
exit 1
