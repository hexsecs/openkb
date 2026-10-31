# OpenKB Specification — v0.1 (draft)

OpenKB is a standard format for **LLM-maintained wikis** ("LLM wikis"): knowledge
bases where raw sources are compiled by an LLM into a set of interlinked
Markdown pages, and kept current by further LLM passes instead of by hand.

The standard has two goals:

1. **Composability.** Any project can connect several KBs and an agent can use
   them together without loading all of them.
2. **Progressive context.** Every KB gives the same tiers of detail, so an agent
   loads the least it needs and goes deeper only when a task calls for it.

The key words MUST, SHOULD and MAY are used as in RFC 2119.

---

## 1. Knowledge base layout

A KB is a directory, usually a git repository:

```
my-kb/
├── kb.yaml          # REQUIRED  manifest (L0)
├── index.md         # REQUIRED  catalog of pages (L1)
├── wiki/            # REQUIRED  pages (L2)
│   ├── some-topic.md
│   └── ...
├── raw/             # OPTIONAL  source material, immutable once added (L3)
├── AGENTS.md        # SHOULD    instructions for the maintainer LLM
└── log.md           # SHOULD    append-only log of ingest / edit / lint passes
```

Anything else (README, LICENSE, CI) is allowed and ignored by consumers.

## 2. Context tiers

| Tier | Source                  | Budget (guide)   | When it is loaded                         |
|------|-------------------------|------------------|-------------------------------------------|
| L0   | `kb.yaml` → `description` | ≤ 300 characters | Always, for every connected KB            |
| L1   | `index.md`              | ≤ 4,000 tokens   | When a task touches the KB's scope        |
| L2   | `wiki/<page>.md`        | ≤ 2,000 tokens per page | When a page is relevant               |
| L3   | `raw/…` or source URLs  | unbounded        | Only to verify or extend a page           |

Consumers MUST be able to work from L0 alone and MUST NOT load L1+ of a KB
just because it is connected. Producers SHOULD respect the budgets; a page
that outgrows its budget SHOULD be split.

## 3. Manifest — `kb.yaml`

```yaml
openkb: "0.1"                 # spec version, REQUIRED
id: awesome-can-bus           # REQUIRED, lowercase, [a-z0-9-], unique per publisher
title: Awesome CAN bus        # REQUIRED
description: >                # REQUIRED, L0 text, ≤ 300 chars
  Tools, libraries and hardware for working with CAN bus...
profile: awesome              # OPTIONAL, see §6 (default: wiki)
version: 2026.10.31           # OPTIONAL, CalVer or SemVer
license: CC-BY-4.0            # SHOULD, SPDX id for the content
maintainers: [hexsecs]        # SHOULD
tags: [can, automotive]       # OPTIONAL
depends: []                   # OPTIONAL, other KB ids this one links into
```

The JSON Schema is in [`schemas/kb.schema.json`](schemas/kb.schema.json).

## 4. Pages — `wiki/*.md`

Each page is Markdown with YAML frontmatter:

```markdown
---
id: python-can                # REQUIRED, equals the file name without .md
title: python-can             # REQUIRED
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

- Links between pages use relative Markdown links (`[cantools](cantools.md)`).
- Links into another KB use `kb://<kb-id>/<page-id>`; consumers resolve them
  only if that KB is connected.
- Claims that are not backed by a source SHOULD be marked, e.g. `(unverified)`.

Schema: [`schemas/page.schema.json`](schemas/page.schema.json).

## 5. Index — `index.md`

`index.md` is the L1 catalog. It MUST list every page as
`- [title](wiki/<id>.md) — <summary>` and MAY group pages under headings.
It SHOULD be generated from page frontmatter, not edited by hand, so it never
drifts from the pages.

## 6. Profiles

A profile adds conventions on top of the base format.

### 6.1 `wiki` (default)

Free-form topic pages: concepts, how-tos, comparisons, decisions.

### 6.2 `awesome` — replacing awesome lists

An awesome-list KB has one page per **entry** (a tool, library, paper,
product...) plus optional topic pages that compare entries. Entry pages add:

```yaml
kind: entry                    # entry | topic
url: https://github.com/...    # REQUIRED for entries
category: Libraries            # REQUIRED for entries, used to group index.md
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

## 7. Maintainer operations

`AGENTS.md` in a KB tells the maintainer LLM how to run three operations.
The names are standard so tools can call them:

| Operation | Input                     | Effect                                                         |
|-----------|---------------------------|----------------------------------------------------------------|
| `ingest`  | a source (file/URL/text)  | add to `raw/` if kept, create/update pages, regenerate index, append to `log.md` |
| `query`   | a question                | answer from L1→L2→L3; MAY file the answer back as a new page   |
| `lint`    | —                         | check schema, broken links, orphan pages, stale sources, budgets; append to `log.md` |

## 8. Connecting KBs to a project

A project lists its KBs in `.openkb/kbs.yaml`:

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

Projects MAY also connect a KB as a git submodule or plain directory; the
cache is just the default.

Schema: [`schemas/project.schema.json`](schemas/project.schema.json).

## 9. Versioning

This spec uses `openkb: "<major>.<minor>"`. Before 1.0, minor versions may
break compatibility.
