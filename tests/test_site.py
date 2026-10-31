import json
import posixpath
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
import yaml

pytest.importorskip("markdown_it")

from conftest import EXAMPLES, page, write  # noqa: E402
from openshelf.cli import main  # noqa: E402
from openshelf.hosting import write_pages_config  # noqa: E402
from openshelf.init import init  # noqa: E402
from openshelf.site import BuildError, build  # noqa: E402


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs, self.ids = [], set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        for key in ("href", "src"):
            if a.get(key):
                self.refs.append(a[key])


def parse(path: Path) -> _Collector:
    c = _Collector()
    c.feed(path.read_text(encoding="utf-8"))
    return c


def broken_links(site: Path) -> list[str]:
    """Every internal href/src (and #fragment) in the site that doesn't resolve."""
    problems = []
    for html_file in site.rglob("*.html"):
        if html_file.name == "404.html":  # uses absolute links by design
            continue
        for ref in parse(html_file).refs:
            parts = urlsplit(ref)
            if parts.scheme or ref.startswith("//"):
                continue
            target = html_file if not parts.path else (html_file.parent / unquote(parts.path))
            if parts.path.endswith("/") or target.is_dir():
                target = target / "index.html"
            rel = html_file.relative_to(site)
            if not target.exists():
                problems.append(f"{rel}: {ref}")
            elif parts.fragment and target.suffix == ".html" and parts.fragment not in parse(target).ids:
                problems.append(f"{rel}: {ref} (no such anchor)")
    return problems


@pytest.mark.parametrize("name", ["awesome-can-bus", "openshelf-design"])
def test_examples_build_with_working_links(tmp_path, name):
    out = tmp_path / "site"
    stats = build(EXAMPLES / name, out)
    assert stats["pages"] >= 3
    assert broken_links(out) == []
    for rel in ("index.html", "index.md", "catalog.json", "llms.txt", "404.html", ".nojekyll", "_assets/style.css", "_assets/search.js"):
        assert (out / rel).is_file(), rel


def test_example_page_urls_follow_ids(tmp_path):
    out = tmp_path / "site"
    build(EXAMPLES / "openshelf-design", out)
    page_html = (out / "topics/llm-wiki/index.html").read_text()
    assert '<a href="../../decisions/manifest-declares-layout/">The manifest declares the layout</a>' in page_html
    assert (out / "topics/llm-wiki/index.md").read_text() == (EXAMPLES / "openshelf-design/kb/topics/llm-wiki.md").read_text()


@pytest.fixture
def kb(tmp_path: Path) -> Path:
    root = init(tmp_path / "kb", id="t", title="Test KB", description="A test KB.")
    with open(root / "kb.yaml", "a") as f:
        f.write("site: https://example.org/t\ndepends: [{id: other, site: 'https://example.org/other/'}, unpublished]\n")
    write(root / "raw/secret.md", "not for publishing\n")
    write(root / "assets/diagram.png", "png")
    write(tmp_path / "outside.md", "a file next to the KB, not in it")
    write(root / "wiki/a.md", page("Alpha", "First page.", body="""
## Set up the bus

See [[b]], [[b|the second page]], [[b#Deep heading]] and [B again](b.md#deep-heading).
[Spaced](my%20page.md), [[old]], [subindex](more.md) and [[#Set up the bus]].
Image: ![diagram](../assets/diagram.png) and embed ![[diagram.png]].
Raw source: [secret](../raw/secret.md). Outside: [out](../../outside.md).
Other KBs: [other](kb://other/thing) and [unpublished](kb://unpublished/thing).
Unsafe: [js](javascript:alert(1)) <script>alert(1)</script> and `[[not-a-link]]`.
""", related="[b, 'other:thing']", sources="[{url: 'https://example.com/a', retrieved: 2026-10-31}, {path: raw/secret.md}]"))
    write(root / "wiki/b.md", page("Beta", "Second page.", body="## Deep heading\n\nText.\n"))
    write(root / "wiki/my page.md", page("Spaced", "Has a space."))
    write(root / "wiki/old.md", "---\nredirect: b\n---\n")
    write(root / "wiki/more.md", "# More pages\n\n- [[my page]]\n")
    write(root / "wiki/e.md", page("Entity", "An entity.", url="https://github.com/x/y", category="Tools", status="archived"))
    write(root / "index.md", "# Test KB\n\n- [[a]] — First.\n- [[b]] — Second.\n- [[e]] — Entity.\n- [More](wiki/more.md)\n")
    return root


def test_links_and_content(tmp_path, kb):
    out = tmp_path / "site"
    assert build(kb, out) == {"pages": 4, "subindexes": 1}  # the redirect stub is not a page
    assert broken_links(out) == []
    a = (out / "a/index.html").read_text()
    for snippet in (
        '<a href="../b/">Beta</a>',                         # unlabeled wikilink shows the title
        '<a href="../b/">the second page</a>',
        '<a href="../b/#deep-heading">',                    # wikilink and Markdown fragments
        '<a href="../my%20page/">Spaced</a>',               # percent-encoded paths
        '<a href="../b/">Beta</a>',                         # redirect is followed
        '<a href="../more/">subindex</a>',
        '<a href="#set-up-the-bus">Set up the bus</a>',
        '<img src="../_files/assets/diagram.png" alt="diagram" />',
        '<img src="../_files/assets/diagram.png" alt="diagram.png">',  # wikilink embed
        '<a href="https://example.org/other/thing/" rel="noopener">other</a>',
        '<a href="../b/#deep-heading">Beta › Deep heading</a>',
        '<span class="broken" title="Link not available on this site">unpublished</span>',
        '<span class="broken" title="Link not available on this site">secret</span>',
        '<span class="broken" title="Link not available on this site">out</span>',
        "&lt;script&gt;alert(1)&lt;/script&gt;",
        "<code>[[not-a-link]]</code>",
        '<link rel="canonical" href="https://example.org/t/a/">',
    ):
        assert snippet in a, snippet
    assert 'href="javascript:' not in a and "<script>alert" not in a  # left as plain text
    assert '<section class="related"><h2>Related</h2><ul><li><a href="../b/">Beta</a></li><li><a href="https://example.org/other/thing/">thing</a></li></ul></section>' in a
    assert "<code>raw/secret.md</code>" in a                # source paths are not published by default
    assert not (out / "_files/raw").exists()
    assert not (out / "_files/outside.md").exists()
    assert 'url=../b/' in (out / "old/index.html").read_text()
    assert "<h1>More pages</h1>" in (out / "more/index.html").read_text()
    e = (out / "e/index.html").read_text()
    assert '<span class="badge status-archived">archived</span>' in e
    assert '<a href="https://github.com/x/y" rel="noopener">https://github.com/x/y</a>' in e


def test_include_sources(tmp_path, kb):
    out = tmp_path / "site"
    build(kb, out, include_sources=True)
    assert (out / "_files/raw/secret.md").is_file()
    assert '<a href="../_files/raw/secret.md">secret</a>' in (out / "a/index.html").read_text()


def test_catalog_and_llms_txt(tmp_path, kb):
    out = tmp_path / "site"
    build(kb, out)
    catalog = json.loads((out / "catalog.json").read_text())
    assert catalog["kb"] == {"id": "t", "title": "Test KB", "description": "A test KB.", "license": "CC-BY-4.0", "site": "https://example.org/t"}
    pages = {p["id"]: p for p in catalog["pages"]}
    assert set(pages) == {"a", "b", "e", "my page"}
    assert pages["a"] == {"id": "a", "title": "Alpha", "summary": "First page.", "type": "concept", "updated": "2026-10-31", "url": "a/", "markdown": "a/index.md"}
    llms = (out / "llms.txt").read_text()
    assert llms.startswith("# Test KB\n\n> A test KB.\n")
    assert "- [Alpha](https://example.org/t/a/index.md): First page." in llms
    assert "- [Spaced](https://example.org/t/my%20page/index.md): Has a space." in llms


def test_llms_txt_relative_without_site(tmp_path):
    out = tmp_path / "site"
    build(EXAMPLES / "awesome-can-bus", out)
    assert "- [cantools](cantools/index.md): " in (out / "llms.txt").read_text()
    assert 'href="/_assets/style.css"' in (out / "404.html").read_text()


def test_output_directory_safety(tmp_path, kb):
    with pytest.raises(BuildError, match="contains the KB"):
        build(kb, kb)
    with pytest.raises(BuildError, match="contains the KB"):
        build(kb, kb.parent)
    with pytest.raises(BuildError, match="must start with '_' or '.'"):
        build(kb, kb / "site")
    build(kb, kb / "_site")
    assert (kb / "_site/index.html").is_file()

    occupied = tmp_path / "occupied"
    write(occupied / "keep.txt", "mine")
    with pytest.raises(BuildError, match="not empty"):
        build(kb, occupied)
    assert (occupied / "keep.txt").exists()
    build(kb, occupied, force=True)
    assert not (occupied / "keep.txt").exists()
    build(kb, occupied)  # a previous build is replaced without --force


def test_cli_build(tmp_path, capsys):
    out = tmp_path / "site"
    assert main(["build", str(EXAMPLES / "awesome-can-bus"), "--out", str(out)]) == 0
    assert "Built 3 pages" in capsys.readouterr().out
    write(tmp_path / "busy/file", "x")
    assert main(["build", str(EXAMPLES / "awesome-can-bus"), "--out", str(tmp_path / "busy")]) == 1


@pytest.mark.parametrize("host,path", [("github", ".github/workflows/openshelf-pages.yml"), ("gitlab", ".gitlab-ci.yml")])
def test_pages_config(tmp_path, host, path):
    dest = write_pages_config(host, tmp_path, kb="docs/my kb", branch="trunk")
    assert dest == tmp_path / path
    config = yaml.safe_load(dest.read_text())
    text = dest.read_text()
    assert "openshelf lint 'docs/my kb'" in text and "openshelf build 'docs/my kb'" in text
    if host == "github":
        assert config[True]["push"]["branches"] == ["trunk"]  # PyYAML reads a bare `on` key as True
        assert config["jobs"]["deploy"]["environment"]["url"] == "${{ steps.deployment.outputs.page_url }}"
        assert config["jobs"]["build"]["steps"][-1]["with"]["path"] == "_site"
    else:
        assert config["pages"]["artifacts"]["paths"] == ["public"]
        assert config["pages"]["rules"] == [{"if": '$CI_COMMIT_BRANCH == "trunk"'}]
    with pytest.raises(FileExistsError):
        write_pages_config(host, tmp_path)
    write_pages_config(host, tmp_path, force=True)


def test_cli_pages(tmp_path, capsys):
    assert main(["pages", "github", "--repo", str(tmp_path)]) == 0
    assert "Source: GitHub Actions" in capsys.readouterr().out
    assert main(["pages", "github", "--repo", str(tmp_path)]) == 1
