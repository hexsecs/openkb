"""Scaffold a new KB with the default layout."""

from __future__ import annotations

from pathlib import Path

import yaml

from . import SPEC_VERSION
from .kb import MANIFEST

AGENTS_TEMPLATE = """\
# Schema for this KB

This is an OpenKB knowledge base (spec {spec}). It follows the LLM Wiki pattern: `raw/` holds immutable sources, `wiki/` is maintained by the LLM, and this file holds the conventions. Refine it as the KB grows.

## Conventions
- Every page has frontmatter with `title`, a one-sentence `summary` (≤ 160 chars), `type` and `updated`.
- Core types: overview, source, entity, concept, comparison, synthesis, answer. Declare any others in `kb.yaml` under `types`.
- Cite sources in `sources`. Never invent facts; mark unsupported claims `(unverified)` and state contradictions openly.
- `index.md` lists every page as `- [Title](wiki/<id>.md) — <summary>`, grouped by category.

## ingest <source>
Save the source in `raw/` if it may be kept, write a `source` page, update every affected page and the index, and append `## [YYYY-MM-DD] ingest | <title>` to `log.md`.

## query <question>
Read `index.md`, then the relevant pages. Answer with links to pages. File useful answers as `answer` pages and log them.

## lint
Run `openkb lint`, then look for contradictions, stale claims, missing pages and missing cross-references. Fix and log.
"""


def init(root: str | Path, *, id: str, title: str, description: str, license: str = "CC-BY-4.0") -> Path:
    root = Path(root)
    if (root / MANIFEST).exists():
        raise FileExistsError(f"{root / MANIFEST} already exists")
    root.mkdir(parents=True, exist_ok=True)
    (root / "wiki").mkdir(exist_ok=True)
    (root / "raw").mkdir(exist_ok=True)
    (root / "raw" / ".gitkeep").touch()
    manifest = {"openkb": SPEC_VERSION, "id": id, "title": title, "description": description, "license": license, "maintainers": []}
    (root / MANIFEST).write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8")
    for name, text in {
        "AGENTS.md": AGENTS_TEMPLATE.format(spec=SPEC_VERSION),
        "index.md": f"# {title}\n\n{description}\n",
        "log.md": "# Log\n",
    }.items():
        if not (root / name).exists():
            (root / name).write_text(text, encoding="utf-8")
    return root
