# OpenKB Specification — v0.1 (draft)

OpenKB standardizes the **LLM Wiki** pattern described by Andrej Karpathy
([gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)).
In that pattern, an LLM incrementally builds and maintains a persistent,
interlinked set of Markdown pages between you and your raw sources, instead of
re-deriving everything from the sources at query time.

The gist is deliberately abstract and leaves layout, page formats and tooling
to each user. OpenKB fixes those choices so that wikis are interchangeable:

1. **Composability.** Any project can connect several KBs and an agent can use
   them together without loading all of them.
2. **Progressive context.** Every KB offers the same tiers of detail, so an agent
   loads the least it needs and goes deeper only when a task calls for it.
3. **Profiles.** Shared conventions for common kinds of wiki, starting with
   `awesome`, which replaces hand-maintained awesome lists.

The key words MUST, SHOULD and MAY are used as in RFC 2119.

---

## 1. The three layers

OpenKB keeps the gist's three layers and gives each a fixed location:

| Layer       | Location                   | Owner                         | Rule                                       |
|-------------|----------------------------|-------------------------------|--------------------------------------------|
| Raw sources | `raw/`                     | human curates                 | Immutable: the LLM reads but never modifies |
| Wiki        | `wiki/`, `index.md`, `log.md` | LLM writes, human reads    | Kept consistent with sources on every pass |
| Schema      | `AGENTS.md` (or `CLAUDE.md`) | human and LLM, co-evolved   | Defines conventions and workflows for this KB |

OpenKB adds a fourth file, the manifest `kb.yaml`, so that tools and other
projects can identify and connect the KB without reading it.

## 2. Layout

```
my-kb/
├── kb.yaml          # REQUIRED  manifest (L0)
├── AGENTS.md        # REQUIRED  schema: conventions and workflows for the maintainer LLM
├── index.md         # REQUIRED  catalog of pages (L1)
├── log.md           # REQUIRED  append-only record of ingests, queries and lint passes
├── wiki/            # REQUIRED  LLM-maintained pages (L2)
│   ├── overview.md  # SHOULD    top-level overview / synthesis of the whole KB
│   └── ...
└── raw/             # OPTIONAL  immutable source documents (L3)
    └── assets/      # OPTIONAL  downloaded images and attachments
```

A KB SHOULD be a git repository. `CLAUDE.md` MAY be used instead of, or as a
pointer to, `AGENTS.md`. Other files (README, LICENSE, CI, `.obsidian/`) are
allowed and ignored by consumers.

Sources MAY live outside the KB (for example as URLs) when they can't be
redistributed; pages then cite them by URL instead of by `raw/` path.

## 3. Context tiers

| Tier | Source                    | Budget (guide)          | When it is loaded                  |
|------|---------------------------|-------------------------|------------------------------------|
| L0   | `kb.yaml` → `description` | ≤ 300 characters        | Always, for every connected KB     |
| L1   | `index.md`                | ≤ 4,000 tokens          | When a task touches the KB's scope |
| L2   | `wiki/<page>.md`          | ≤ 2,000 tokens per page | When a page is relevant            |
| L3   | `raw/…` or source URLs    | unbounded               | Only to verify or extend a page    |

Consumers MUST be able to work from L0 alone and MUST NOT load L1+ of a KB
just because it is connected. Producers SHOULD respect the budgets; a page
that outgrows its budget SHOULD be split.

The gist notes that a plain index works well up to roughly 100 sources. A KB
whose `index.md` exceeds the L1 budget SHOULD either nest it (`index.md`
links to per-category indexes such as `wiki/index-<category>.md`) or rely on a
search tool (§9), and say which in `AGENTS.md`.

## 4. Manifest — `kb.yaml`

```yaml
openkb: "0.1"                 # spec version, REQUIRED
id: awesome-can-bus           # REQUIRED, lowercase, [a-z0-9-], unique per publisher
title: Awesome CAN bus        # REQUIRED
description: >                # REQUIRED, L0 text, ≤ 300 chars
  Tools, libraries and hardware for working with CAN bus...
profile: awesome              # OPTIONAL, see §7 (default: wiki)
version: 2026.10.31           # OPTIONAL, CalVer or SemVer
license: CC-BY-4.0            # SHOULD, SPDX id for the wiki content
maintainers: [hexsecs]        # SHOULD
tags: [can, automotive]       # OPTIONAL
depends: []                   # OPTIONAL, other KB ids this one links into
```

Schema: [`schemas/kb.schema.json`](schemas/kb.schema.json).

## 5. Pages — `wiki/*.md`

Each page is Markdown with YAML frontmatter (compatible with Obsidian and
Dataview):

```markdown
---
id: python-can                # REQUIRED, equals the file name without .md
title: python-can             # REQUIRED
type: entity                  # REQUIRED, see below
summary: Python library ...   # REQUIRED, ≤ 160 chars, reused verbatim in index.md
tags: [library, python]       # OPTIONAL
related: [cantools]           # OPTIONAL, page ids in this KB, or "<kb-id>:<page-id>"
sources:                      # SHOULD, where the claims come from
  - url: https://pypi.org/project/python-can/
    retrieved: 2026-10-31
updated: 2026-10-31           # REQUIRED, last substantive change
---

Body...
```

### 5.1 Page types

These are the page types the gist names, plus `answer` for filed-back queries:

| `type`       | Purpose                                                            |
|--------------|--------------------------------------------------------------------|
| `overview`   | Top-level overview of the KB or a large area of it                 |
| `source`     | Summary of one raw source; its `sources` cites that source         |
| `entity`     | A concrete thing: a tool, person, organization, product, paper     |
| `concept`    | An idea, technique or term                                         |
| `comparison` | Side-by-side of several entities or concepts                       |
| `synthesis`  | Conclusions drawn across many sources                              |
| `answer`     | A query answer filed back into the wiki (§8)                       |

### 5.2 Links

- Within a KB, pages MAY use relative Markdown links (`[cantools](cantools.md)`)
  or wikilinks (`[[cantools]]`); consumers MUST resolve both to `wiki/<id>.md`.
  Markdown links render on GitHub; wikilinks suit Obsidian.
- Links into another KB use `kb://<kb-id>/<page-id>`; consumers resolve them
  only if that KB is connected.
- Claims that no source backs SHOULD be marked, e.g. `(unverified)`.
  Contradictions between sources SHOULD be stated on the page, not silently
  resolved.

Schema: [`schemas/page.schema.json`](schemas/page.schema.json).

## 6. Index and log

### `index.md`

The L1 catalog, and the first thing the LLM reads when answering a query. It
MUST list every page as `- [title](wiki/<id>.md) — <summary>`, grouped under
category headings. It SHOULD be regenerated from page frontmatter on every
ingest, so it never drifts from the pages.

### `log.md`

Append-only, chronological. Each entry starts with a heading in this exact
form, so the log can be parsed with standard Unix tools:

```markdown
## [2026-10-31] ingest | python-can PyPI page
Created wiki/python-can.md; updated wiki/socketcan.md, index.md.
```

The operation is one of `ingest`, `query` or `lint`.

## 7. Profiles

A profile adds conventions on top of the base format.

### 7.1 `wiki` (default)

The general pattern from the gist: any mix of the page types in §5.1.

### 7.2 `awesome` — replacing awesome lists

Each list entry is an `entity` page, plus optional `comparison` and `concept`
pages. Entity pages in this profile add:

```yaml
url: https://github.com/...    # REQUIRED for entities
category: Libraries            # REQUIRED for entities, used to group index.md
license: MIT                   # OPTIONAL, SPDX id of the thing being listed
status: active                 # active | maintenance | archived | unknown
last_checked: 2026-10-31       # when url/status were last verified
```

What this gives over a flat awesome list:

- Each entry has an LLM-written summary, comparison links and sources, not
  just one line.
- Adding an entry is an *ingest*: a contributor submits a URL, the maintainer
  LLM writes or updates the page, links it to related entries and regenerates
  the index.
- A *lint* pass rechecks `url`, `status` and `last_checked`, and flags dead or
  archived entries.
- `index.md` doubles as the classic awesome-list README, so nothing is lost
  for human readers.

## 8. Operations

`AGENTS.md` tells the maintainer LLM how to run three operations. The names
are standard so tools can call them, and every run appends to `log.md`.

| Operation | Input                    | Effect |
|-----------|--------------------------|--------|
| `ingest`  | a source (file/URL/text) | Store it in `raw/` if it may be kept; write a `source` page; create or update every affected `entity`, `concept`, `comparison` and `synthesis` page (one source often touches 10–15); regenerate `index.md`. MAY run one source at a time with the human reviewing, or in batches. |
| `query`   | a question               | Read `index.md`, then relevant pages, then sources if needed; answer with citations to pages. A useful answer SHOULD be filed back as an `answer` page, so explorations compound. |
| `lint`    | —                        | Check schema conformance, contradictions between pages, stale claims, orphan pages, missing concept pages, missing cross-references, broken links, tier budgets and data gaps worth filling (for example by web search). |

## 9. Tooling (non-normative)

The format works with no tools beyond an LLM agent and a text editor. Useful
additions, as suggested in the gist:

- **Search** over the wiki once `index.md` alone isn't enough, for example
  [qmd](https://github.com/tobi/qmd) (hybrid BM25/vector search, CLI and MCP)
  or a small custom script.
- **Obsidian** for reading (graph view shows hubs and orphans), Obsidian Web
  Clipper for turning articles into Markdown sources, and Dataview for
  querying frontmatter.
- **git** for history and collaboration.

## 10. Connecting KBs to a project

This is OpenKB's main addition to the pattern. A project lists its KBs in
`.openkb/kbs.yaml`:

```yaml
openkb: "0.1"
kbs:
  - id: awesome-can-bus
    source: github:hexsecs/awesome-can-bus   # github:owner/repo, git URL, or local path
    ref: main                                # branch, tag or commit
    path: .                                  # OPTIONAL, subdirectory holding kb.yaml
    use: when the task involves CAN tooling  # OPTIONAL, hint shown with the L0 text
```

A tool (CLI, MCP server or agent hook) then:

1. Fetches each KB into `.openkb/cache/<id>/` (gitignored), pinned in
   `.openkb/kbs.lock`.
2. Writes `.openkb/context.md`: one block per KB with its L0 text, the `use`
   hint, and the path to its `index.md`.
3. The project's `AGENTS.md` / `CLAUDE.md` includes or links
   `.openkb/context.md`, so the agent always sees L0 and knows how to go
   deeper.

Connected KBs are read-only from the project's side. Knowledge gained while
working on the project goes back to a KB as an `ingest` or a filed `answer`
in that KB's own repository.

Projects MAY also connect a KB as a git submodule or plain directory; the
cache is just the default.

Schema: [`schemas/project.schema.json`](schemas/project.schema.json).

## 11. Versioning

This spec uses `openkb: "<major>.<minor>"`. Before 1.0, minor versions may
break compatibility.
