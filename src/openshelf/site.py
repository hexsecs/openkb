"""Render a KB as a static website: HTML for people, Markdown, catalog.json and llms.txt for agents.

Each page is published at `<page-id>/`, so page ids double as stable URLs, and every
link is relative, so the site works under any base path (e.g. a GitHub Pages project site).
"""

from __future__ import annotations

import html
import json
import posixpath
import re
import shutil
from datetime import date, datetime
from functools import partial
from pathlib import Path
from urllib.parse import quote, unquote

from markdown_it import MarkdownIt
from markdown_it.rules_inline import StateInline

from . import SPEC_VERSION, __version__
from .kb import KB, KBError, Page

MARKER = ".openshelf-site"
ASSETS = Path(__file__).parent / "site_assets"
_SAFE_URL = re.compile(r"^(https?:|mailto:)", re.IGNORECASE)
_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
_WIKILINK = re.compile(r"(!?)\[\[([^\[\]\n]+?)\]\]")


class BuildError(Exception):
    pass


def slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[\s_-]+", "-", slug) or "section"


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _wikilink_rule(state: StateInline, silent: bool) -> bool:
    if not state.src.startswith(("[[", "![["), state.pos):
        return False
    m = _WIKILINK.match(state.src, state.pos)
    if not m:
        return False
    if not silent:
        target, _, label = m.group(2).partition("|")
        target, _, fragment = target.partition("#")
        target, fragment = target.strip(), fragment.strip()
        token = state.push("wikilink", "", 0)
        token.meta = {
            "target": target,
            "fragment": fragment,
            "label": label.strip() or (target.rsplit("/", 1)[-1] if target else fragment),
            "labeled": bool(label.strip()),
            "embed": m.group(1) == "!",
        }
    state.pos = m.end()
    return True


def _heading_ids(state) -> None:
    seen: dict[str, int] = {}
    tokens = state.tokens
    for i, token in enumerate(tokens):
        if token.type == "heading_open":
            slug = slugify(tokens[i + 1].content)
            n = seen.get(slug, 0)
            seen[slug] = n + 1
            token.attrSet("id", slug if n == 0 else f"{slug}-{n}")


class Builder:
    def __init__(self, kb: KB, out: Path, *, include_sources: bool = False):
        self.kb = kb
        self.out = out
        self.include_sources = include_sources
        self.sites: dict[str, str] = {}
        for dep in kb.manifest.get("depends") or []:
            if isinstance(dep, dict) and dep.get("id") and dep.get("site"):
                self.sites[str(dep["id"])] = str(dep["site"]).rstrip("/")
        self.site_url = str(kb.manifest.get("site") or "").rstrip("/")
        self.pages_dir = kb.path("pages")
        self.md = MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"])
        self.md.inline.ruler.before("link", "wikilink", _wikilink_rule)
        self.md.core.ruler.push("heading_ids", _heading_ids)
        renderer = self.md.renderer
        for name, rule in (("wikilink", self._render_wikilink), ("link_open", self._render_link_open),
                           ("link_close", self._render_link_close), ("image", self._render_image)):
            renderer.rules[name] = partial(rule, renderer)

    # -- URLs ---------------------------------------------------------------

    @staticmethod
    def href(from_dir: str, to: str, *, is_dir: bool = True) -> str:
        rel = posixpath.relpath(to or ".", from_dir or ".")
        if is_dir:
            return "./" if rel == "." else quote(rel) + "/"
        return quote(rel)

    def subindex_id(self, path: Path) -> str:
        return path.relative_to(self.pages_dir).with_suffix("").as_posix()

    def copy_file(self, path: Path) -> str | None:
        """Copy an attachment into the site; return its site path, or None if it may not be published."""
        path = path.resolve()
        root = self.kb.root
        if root not in path.parents or not path.is_file():
            return None
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts) or rel.as_posix() == "kb.yaml":
            return None
        sources = self.kb.path("sources")
        if not self.include_sources and (sources == path or sources in path.parents):
            return None
        dest = self.out / "_files" / rel
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
        return f"_files/{rel.as_posix()}"

    def link_url(self, source: Path, style: str, target: str, fragment: str, from_dir: str) -> str | None:
        """Where a link in `source` should point in the site, or None if it can't be followed."""
        if style == "md":
            if target.startswith("#"):
                return target
            if _SCHEME.match(target) and not target.startswith("kb://"):
                return target if _SAFE_URL.match(target) else None
            target, _, fragment = target.partition("#")
            target, fragment = unquote(target), unquote(fragment)
        link = self.kb.resolve(source, style, target)
        anchor = f"#{slugify(fragment)}" if fragment else ""
        if link.kind == "page":
            final = self.kb.follow(link.target)
            return self.href(from_dir, final) + anchor if final else None
        if link.kind == "subindex":
            return self.href(from_dir, self.subindex_id(Path(link.target))) + anchor
        if link.kind == "file":
            site_path = self.copy_file(Path(link.target))
            return self.href(from_dir, site_path, is_dir=False) if site_path else None
        if link.kind == "kb":
            other, _, page = link.target.partition("/")
            if other == self.kb.id and page in self.kb.pages:
                final = self.kb.follow(page)
                return self.href(from_dir, final) + anchor if final else None
            site = self.sites.get(other)
            return f"{site}/{quote(page)}/{anchor}" if site and page else None
        return None

    # -- Markdown render rules ---------------------------------------------

    def _render_link_open(self, renderer, tokens, idx, options, env):
        token = tokens[idx]
        url = self.link_url(env["source"], "md", token.attrGet("href") or "", "", env["from_dir"])
        if url is None:
            env["broken"] = True
            return '<span class="broken" title="Link not available on this site">'
        env["broken"] = False
        token.attrSet("href", url)
        if _SAFE_URL.match(url):
            token.attrSet("rel", "noopener")
        return renderer.renderToken(tokens, idx, options, env)

    def _render_link_close(self, renderer, tokens, idx, options, env):
        return "</span>" if env.pop("broken", False) else "</a>"

    def _render_image(self, renderer, tokens, idx, options, env):
        token = tokens[idx]
        alt = renderer.renderInlineAsText(token.children or [], options, env)
        url = self.link_url(env["source"], "md", token.attrGet("src") or "", "", env["from_dir"])
        if url is None:
            return f'<span class="broken">{_esc(alt)}</span>'
        token.attrSet("src", url)
        return renderer.image(tokens, idx, options, env)

    def _render_wikilink(self, renderer, tokens, idx, options, env):
        meta = tokens[idx].meta
        if not meta["target"]:  # [[#Heading]] in the same page
            return f'<a href="#{_esc(slugify(meta["fragment"]))}">{_esc(meta["label"])}</a>'
        url = self.link_url(env["source"], "wiki", meta["target"], meta["fragment"], env["from_dir"])
        if url is None:
            return f'<span class="broken" title="Link not available on this site">{_esc(meta["label"])}</span>'
        label = meta["label"]
        if not meta["labeled"]:
            link = self.kb.resolve(env["source"], "wiki", meta["target"])
            final = self.kb.follow(link.target) if link.kind == "page" else None
            if final:
                label = str((self.kb.pages[final].meta or {}).get("title", label))
                if meta["fragment"]:
                    label = f"{label} › {meta['fragment']}"
        if meta["embed"] and Path(meta["target"]).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".avif"}:
            return f'<img src="{_esc(url)}" alt="{_esc(label)}">'
        return f'<a href="{_esc(url)}">{_esc(label)}</a>'

    def render(self, text: str, source: Path, from_dir: str, *, drop_h1: bool) -> tuple[str, str | None]:
        """Render Markdown; return (html, text of a leading h1 if one was dropped)."""
        env = {"source": source, "from_dir": from_dir}
        tokens = self.md.parse(text, env)
        h1 = None
        if drop_h1 and len(tokens) >= 3 and tokens[0].type == "heading_open" and tokens[0].tag == "h1":
            h1 = tokens[1].content
            tokens = tokens[3:]
        return self.md.renderer.render(tokens, self.md.options, env), h1

    # -- Page assembly -----------------------------------------------------

    def layout(self, from_dir: str, title: str, body: str, *, description: str = "", canonical: str = "",
               markdown: str = "", root: str | None = None) -> str:
        root = _esc(root) if root is not None else self.href(from_dir, "")
        kb_title = self.kb.title
        full_title = kb_title if title == kb_title else f"{title} · {kb_title}"
        head = [
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{_esc(full_title)}</title>",
            f'<meta name="generator" content="OpenShelf {_esc(__version__)}">',
            f'<link rel="stylesheet" href="{root}_assets/style.css">',
        ]
        if description:
            head.append(f'<meta name="description" content="{_esc(description)}">')
        if canonical and self.site_url:
            head.append(f'<link rel="canonical" href="{_esc(self.site_url + "/" + canonical)}">')
        if markdown:
            head.append(f'<link rel="alternate" type="text/markdown" href="{_esc(markdown)}">')
        license_ = self.kb.manifest.get("license")
        footer = [f'<a href="{root}">{_esc(kb_title)}</a>']
        if license_:
            footer.append(f"Content license: {_esc(license_)}")
        footer.append(f'<a href="{root}llms.txt">llms.txt</a>')
        footer.append('Built with <a href="https://github.com/hexsecs/openshelf" rel="noopener">OpenShelf</a>')
        return (
            "<!doctype html>\n<html lang=\"en\">\n<head>\n" + "\n".join(head) + "\n</head>\n<body>\n"
            f'<header class="site-header"><a class="brand" href="{root}">{_esc(kb_title)}</a>'
            f'<div class="search" data-root="{root}"><input type="search" placeholder="Search pages" aria-label="Search pages" autocomplete="off">'
            '<ul class="results" role="listbox" hidden></ul></div></header>\n'
            f"<main>\n{body}\n</main>\n"
            f'<footer class="site-footer">{" · ".join(footer)}</footer>\n'
            f'<script src="{root}_assets/search.js" defer></script>\n</body>\n</html>\n'
        )

    def facts(self, page: Page, from_dir: str) -> str:
        meta = page.meta or {}
        rows: list[tuple[str, str]] = []
        if meta.get("type"):
            rows.append(("Type", _esc(meta["type"])))
        url = str(meta.get("url") or "")
        if url:
            rows.append(("Link", f'<a href="{_esc(url)}" rel="noopener">{_esc(url)}</a>' if _SAFE_URL.match(url) else _esc(url)))
        for key, label in (("category", "Category"), ("license", "License")):
            if meta.get(key):
                rows.append((label, _esc(meta[key])))
        if meta.get("status"):
            status = str(meta["status"])
            rows.append(("Status", f'<span class="badge status-{_esc(slugify(status))}">{_esc(status)}</span>'))
        if meta.get("last_checked"):
            rows.append(("Last checked", _esc(meta["last_checked"])))
        if meta.get("updated"):
            rows.append(("Updated", _esc(meta["updated"])))
        if not rows:
            return ""
        items = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows)
        return f'<dl class="facts">{items}</dl>'

    def related(self, page: Page, from_dir: str) -> str:
        items = []
        for ref in (page.meta or {}).get("related") or []:
            ref = str(ref)
            if ":" in ref:
                other, _, pid = ref.partition(":")
                url = self.link_url(page.path, "md", f"kb://{other}/{pid}", "", from_dir)
                label = pid.rsplit("/", 1)[-1]
            else:
                url = self.link_url(page.path, "wiki", ref, "", from_dir)
                final = self.kb.follow(ref) if ref in self.kb.pages else None
                label = (self.kb.pages[final].meta or {}).get("title", ref) if final else ref
            items.append(f'<li><a href="{_esc(url)}">{_esc(label)}</a></li>' if url else f'<li><span class="broken">{_esc(label)}</span></li>')
        return f'<section class="related"><h2>Related</h2><ul>{"".join(items)}</ul></section>' if items else ""

    def sources(self, page: Page, from_dir: str) -> str:
        items = []
        for src in (page.meta or {}).get("sources") or []:
            if not isinstance(src, dict):
                continue
            retrieved = f' <span class="muted">(retrieved {_esc(src["retrieved"])})</span>' if src.get("retrieved") else ""
            if src.get("url"):
                url = str(src["url"])
                link = f'<a href="{_esc(url)}" rel="noopener">{_esc(url)}</a>' if _SAFE_URL.match(url) else _esc(url)
            elif src.get("path"):
                site_path = self.copy_file(self.kb.root / str(src["path"]))
                link = (f'<a href="{_esc(self.href(from_dir, site_path, is_dir=False))}">{_esc(src["path"])}</a>'
                        if site_path else f"<code>{_esc(src['path'])}</code>")
            else:
                continue
            items.append(f"<li>{link}{retrieved}</li>")
        return f'<section class="sources"><h2>Sources</h2><ul>{"".join(items)}</ul></section>' if items else ""

    def redirect_page(self, from_dir: str, target_id: str) -> str:
        url = self.href(from_dir, target_id)
        return (
            '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            f'<meta http-equiv="refresh" content="0; url={_esc(url)}"><link rel="canonical" href="{_esc(url)}">'
            f'<title>Moved</title></head><body><p>This page moved to <a href="{_esc(url)}">{_esc(target_id)}</a>.</p></body></html>\n'
        )

    # -- Build -------------------------------------------------------------

    def write(self, rel: str, text: str) -> None:
        dest = self.out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")

    def build(self) -> dict:
        kb = self.kb
        index = kb.path("index")
        if not index.is_file():
            raise BuildError(f"{kb.root}: no index at {kb.layout['index']}")
        catalog_pages = []
        for pid, page in kb.pages.items():
            meta = page.meta or {}
            if page.redirect or "__error__" in meta:
                continue
            catalog_pages.append({
                "id": pid,
                "title": str(meta.get("title", pid)),
                "summary": str(meta.get("summary", "")),
                "type": meta.get("type"),
                "updated": meta.get("updated"),
                "url": self.href("", pid),
                "markdown": self.href("", pid) + "index.md",
            })

        # Home page.
        text = index.read_text(encoding="utf-8")
        body, _ = self.render(text, index, "", drop_h1=True)
        home = (f'<article class="home"><h1>{_esc(kb.title)}</h1><p class="summary">{_esc(kb.description)}</p>'
                f'<div class="content">{body}</div></article>')
        self.write("index.html", self.layout("", kb.title, home, description=kb.description, canonical="", markdown="index.md"))
        self.write("index.md", text)

        # Sub-indexes.
        for path in sorted(kb.subindexes):
            sid = self.subindex_id(path)
            text = path.read_text(encoding="utf-8")
            body, h1 = self.render(text, path, sid, drop_h1=True)
            title = h1 or path.stem
            article = f'<article><h1>{_esc(title)}</h1><div class="content">{body}</div></article>'
            self.write(f"{sid}/index.html", self.layout(sid, title, article, canonical=f"{quote(sid)}/", markdown="index.md"))
            self.write(f"{sid}/index.md", text)

        # Pages and redirect stubs.
        for pid, page in kb.pages.items():
            meta = page.meta or {}
            if page.redirect:
                final = kb.follow(pid)
                if final:
                    self.write(f"{pid}/index.html", self.redirect_page(pid, final))
                continue
            if "__error__" in meta:
                continue
            title = str(meta.get("title", pid))
            summary = str(meta.get("summary", ""))
            body, _ = self.render(page.body, page.path, pid, drop_h1=False)
            article = (
                f'<article><h1>{_esc(title)}</h1>'
                + (f'<p class="summary">{_esc(summary)}</p>' if summary else "")
                + self.facts(page, pid)
                + f'<div class="content">{body}</div>'
                + self.related(page, pid)
                + self.sources(page, pid)
                + "</article>"
            )
            self.write(f"{pid}/index.html", self.layout(pid, title, article, description=summary, canonical=f"{quote(pid)}/", markdown="index.md"))
            self.write(f"{pid}/index.md", page.path.read_text(encoding="utf-8"))

        # Machine-readable outputs.
        base = self.site_url + "/" if self.site_url else ""
        catalog = {
            "openshelf": SPEC_VERSION,
            "kb": {k: kb.manifest[k] for k in ("id", "title", "description", "profile", "license", "site") if k in kb.manifest},
            "pages": catalog_pages,
        }
        self.write("catalog.json", json.dumps(catalog, indent=1, default=_json_default, ensure_ascii=False) + "\n")
        lines = [f"# {kb.title}", "", f"> {kb.description}", ""]
        if kb.manifest.get("license"):
            lines += [f"Content license: {kb.manifest['license']}.", ""]
        lines += [f"- [Index]({base}index.md): the catalog of pages, organized by topic", "", "## Pages", ""]
        lines += [f"- [{p['title']}]({base}{p['markdown']}): {p['summary']}" for p in catalog_pages]
        self.write("llms.txt", "\n".join(lines) + "\n")

        # 404.html is served at any depth, so it needs absolute links: the site URL if known.
        home_url = f"{self.site_url}/" if self.site_url else "/"
        not_found = f'<article><h1>Page not found</h1><p>Try the search box, or start from the <a href="{_esc(home_url)}">home page</a>.</p></article>'
        self.write("404.html", self.layout("", "Page not found", not_found, root=home_url))
        shutil.copytree(ASSETS, self.out / "_assets", dirs_exist_ok=True)
        (self.out / ".nojekyll").touch()
        return {"pages": len(catalog_pages), "subindexes": len(kb.subindexes)}


def _json_default(value: object) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def prepare_out(out: Path, kb_root: Path, *, force: bool = False) -> Path:
    out = out.resolve()
    kb_root = kb_root.resolve()
    if out == kb_root or out in kb_root.parents:
        raise BuildError(f"refusing to build into {out}: it contains the KB itself")
    if kb_root in out.parents:
        first = out.relative_to(kb_root).parts[0]
        if not first.startswith(("_", ".")):
            raise BuildError(f"an output directory inside the KB must start with '_' or '.' so it isn't read as pages (e.g. _site), not '{first}'")
    if out.exists():
        if not out.is_dir():
            raise BuildError(f"{out} is not a directory")
        if any(out.iterdir()) and not (out / MARKER).exists() and not force:
            raise BuildError(f"{out} is not empty and wasn't created by openshelf build; pass --force to replace it")
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / MARKER).write_text("Built by openshelf build. This directory is replaced on every build.\n", encoding="utf-8")
    return out


def build(kb_root: str | Path, out: str | Path, *, force: bool = False, include_sources: bool = False) -> dict:
    try:
        kb = KB(kb_root)
    except KBError as e:
        raise BuildError(str(e)) from e
    out_path = prepare_out(Path(out), kb.root, force=force)
    return Builder(kb, out_path, include_sources=include_sources).build()
