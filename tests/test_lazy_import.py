"""E4: o caminho leve não pode importar torch no nível de módulo.

Roda mesmo no .venv que TEM torch instalado: se qualquer módulo leve fizer
`import torch` no topo, torch aparece em sys.modules após o import — e falha aqui.
"""

import sys
import subprocess


LIGHT_MODULES = [
    "atado",
    "atado.cli",
    "atado.config",
    "atado.models",
    "atado.glossary",
    "atado.merge",
    "atado.terms",
    "atado.redact",
    "atado.interview",
    "atado.workspace",
    "atado.timeutil",
]


def test_light_modules_do_not_import_torch():
    # subprocesso limpo para não sofrer contaminação de outros testes
    code = (
        "import importlib, sys\n"
        f"for m in {LIGHT_MODULES!r}:\n"
        "    importlib.import_module(m)\n"
        "assert 'torch' not in sys.modules, 'torch foi importado no caminho leve!'\n"
        "print('ok')\n"
    )
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert "ok" in res.stdout
