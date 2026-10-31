"""Check a KB against the OpenShelf contract (errors) and conventions (warnings)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import jsonschema

from .kb import KB, KBError

CORE_TYPES = {"overview", "source", "entity", "concept", "comparison", "synthesis", "answer"}
INDEX_TOKEN_BUDGET = 4000
PAGE_TOKEN_BUDGET = 2000


@dataclass
class Issue:
    level: str  # error | warning
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.level}: {self.where}: {self.message}"


def schema_dir() -> Path:
    bundled = Path(__file__).parent / "schemas"
    return bundled if bundled.is_dir() else Path(__file__).resolve().parents[2] / "schemas"


@cache
def validator(name: str) -> jsonschema.protocols.Validator:
    schema = json.loads((schema_dir() / name).read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())


def estimate_tokens(text: str) -> int:
    return len(text) // 4


def _schema_messages(name: str, data: object) -> list[str]:
    out = []
    for e in validator(name).iter_errors(data):
        loc = "/".join(str(p) for p in e.absolute_path)
        out.append(f"{loc}: {e.message}" if loc else e.message)
    return out


def lint(root: str | Path) -> list[Issue]:
    try:
        kb = KB(root)
    except KBError as e:
        return [Issue("error", str(root), str(e))]
    issues: list[Issue] = []

    def err(where: str, msg: str) -> None:
        issues.append(Issue("error", where, msg))

    def warn(where: str, msg: str) -> None:
        issues.append(Issue("warning", where, msg))

    m = kb.manifest
    for msg in _schema_messages("kb.schema.json", json.loads(json.dumps(m, default=str))):
        err("kb.yaml", msg)
    for field in ("license", "maintainers"):
        if field not in m:
            warn("kb.yaml", f"no {field}")

    pages_dir, index = kb.path("pages"), kb.path("index")
    if not pages_dir.is_dir():
        err("kb.yaml", f"layout.pages directory not found: {kb.layout['pages']}")
    if not index.is_file():
        err("kb.yaml", f"layout.index not found: {kb.layout['index']}")
        return issues

    declared = m.get("types") if isinstance(m.get("types"), dict) else {}
    depends = {d.get("id") if isinstance(d, dict) else d for d in m.get("depends") or []}
    rel = lambda p: p.relative_to(kb.root).as_posix()  # noqa: E731

    def check_links(path: Path, text: str) -> list:
        found = kb.links(path, text)
        for link in found:
            if link.kind == "missing":
                err(rel(path), f"unresolved link {link.raw}")
            elif link.kind == "ambiguous":
                warn(rel(path), f"ambiguous wikilink {link.raw}; use the full page id")
            elif link.kind == "page" and kb.follow(link.target) is None:
                err(rel(path), f"link {link.raw} leads to a broken redirect")
            elif link.kind == "kb":
                other = link.target.split("/", 1)[0]
                if other != kb.id and other not in depends:
                    warn(rel(path), f"links into KB '{other}', which is not listed in depends")
        return found

    # Pages reachable from the index, directly or through sub-indexes.
    reachable: set[str] = set()
    for path in [index, *sorted(kb.subindexes)]:
        text = path.read_text(encoding="utf-8")
        for link in check_links(path, text):
            if link.kind == "page" and (final := kb.follow(link.target)):
                reachable.update({link.target, final})
        if path == index and estimate_tokens(text) > INDEX_TOKEN_BUDGET:
            warn(rel(path), f"index is ~{estimate_tokens(text)} tokens, over the L1 budget of {INDEX_TOKEN_BUDGET}; split into sub-indexes")

    for pid, page in kb.pages.items():
        where = rel(page.path)
        meta = page.meta
        if meta is None:
            err(where, "no frontmatter")
            continue
        if "__error__" in meta:
            err(where, f"invalid frontmatter: {meta['__error__']}")
            continue
        meta = json.loads(json.dumps(meta, default=str))
        for msg in _schema_messages("page.schema.json", meta):
            err(where, msg)
        if page.redirect:
            if kb.follow(pid) is None:
                err(where, f"redirect to missing page '{page.redirect}'")
            continue
        check_links(page.path, page.body)
        if pid not in reachable:
            err(where, "not reachable from the index")
        for field in ("type", "updated"):
            if field not in meta:
                warn(where, f"no {field}")
        ptype = meta.get("type")
        if isinstance(ptype, str) and ptype not in CORE_TYPES and ptype not in declared:
            warn(where, f"type '{ptype}' is not a core type and is not declared in kb.yaml types")
        if estimate_tokens(page.body) > PAGE_TOKEN_BUDGET:
            warn(where, f"page is ~{estimate_tokens(page.body)} tokens, over the L2 budget of {PAGE_TOKEN_BUDGET}; consider splitting")
        if kb.profile == "awesome" and ptype == "entity":
            for field in ("url", "category"):
                if field not in meta:
                    err(where, f"awesome profile: entity needs {field}")
            for field in ("status", "last_checked"):
                if field not in meta:
                    warn(where, f"awesome profile: entity has no {field}")

    return issues
