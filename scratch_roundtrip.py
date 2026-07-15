import sys, textwrap
from atado.interview import parse_agent_output, import_into_config, SENTINELS
from atado.config import load_config, load_commented, dumps_commented
import tempfile, os

# minimal cfg
cfg_text = 'project: "T"\nglossary:\n  context: ""\n  terms: []\n'
fd, path = tempfile.mkstemp(suffix=".yaml"); os.write(fd, cfg_text.encode()); os.close(fd)
cfg = load_config(path)

from atado.kit import render_protocol
proto = render_protocol(cfg, has_suspects=True, diarized=True)
print("=== rendered protocol heads ===")
for ln in proto.splitlines():
    if ln.startswith("## ") and any(s in ln for s in ("TABELA","NARRATIVA","PEND")):
        print(repr(ln))
print("=== parse whole protocol ===")
parsed = parse_agent_output(proto)
import json
print(json.dumps(parsed["tabela"], ensure_ascii=False, indent=2))
print("narrativa (first 60):", repr(parsed["narrativa"][:60]))
print("pendencias (first 60):", repr(parsed["pendencias"][:60]))
