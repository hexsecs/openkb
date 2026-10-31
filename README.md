# OpenKB

An open standard for the **LLM Wiki** pattern described by [Andrej Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): an LLM builds and maintains a persistent, interlinked Markdown wiki from your raw sources, so knowledge is compiled once and kept current instead of re-derived on every query.

The gist leaves layout, page formats and tooling open, and OpenKB keeps it that way. It standardizes only what's needed to **connect** knowledge bases, and leaves everything else to the KB's owner:

- **A small contract.** A `kb.yaml` manifest at the root declares the KB's description and where its pages, index and sources are. Pages need only a `title` and a one-line `summary`, and are identified by their path. Links can be Markdown or Obsidian wikilinks; links into other KBs use `kb://<kb>/<page>`.
- **Free organization.** Folders, page types, naming and workflows are up to you. The spec offers conventions from the gist (default layout, page types, ingest/query/lint, log format) that you can adopt, adapt or ignore.
- **Progressive context.** Every KB offers the same four tiers: a one-line description (L0), the index (L1), pages (L2) and raw sources (L3). Agents load only as deep as the task needs, so a project can connect many KBs cheaply.
- **Connect many KBs to a project.** List them in `.openkb/kbs.yaml`; tooling turns that into a short `context.md` the project's agent always sees.
- **Awesome lists, upgraded.** The opt-in `awesome` profile makes each list entry a sourced, cross-linked page that an LLM keeps current, while the index still reads as a classic awesome list.

## Contents

- [`SPEC.md`](SPEC.md): the v0.1 draft spec
- [`schemas/`](schemas/): JSON Schemas for `kb.yaml`, page frontmatter and `.openkb/kbs.yaml`
- [`examples/awesome-can-bus/`](examples/awesome-can-bus/): a small awesome-profile KB using the default layout
- [`examples/openkb-design/`](examples/openkb-design/): a KB with its own layout (nested folders, wikilinks, a custom page type)
- [`examples/project/`](examples/project/): a project that connects both

## Status

Draft. Planned next: a CLI (`openkb add | sync | index | lint`) and an MCP server that exposes connected KBs tier by tier.
