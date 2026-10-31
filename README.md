# OpenKB

An open standard for the **LLM Wiki** pattern described by [Andrej Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): an LLM builds and maintains a persistent, interlinked Markdown wiki from your raw sources, so knowledge is compiled once and kept current instead of re-derived on every query.

The gist leaves the layout, page formats and tooling to each user. OpenKB fixes them so that LLM wikis are interchangeable:

- **One format.** Raw sources in `raw/`, LLM-maintained pages in `wiki/`, the schema in `AGENTS.md`, plus `index.md`, `log.md` and a small `kb.yaml` manifest. Pages have typed frontmatter (`entity`, `concept`, `comparison`, `synthesis`...), compatible with Obsidian.
- **Progressive context.** Each KB offers four tiers: a one-line description (L0), the index (L1), pages (L2) and raw sources (L3). Agents load only as deep as the task needs, so a project can connect many KBs cheaply.
- **Connect many KBs to a project.** List them in `.openkb/kbs.yaml`; tooling turns that into a short `context.md` the project's agent always sees.
- **Awesome lists, upgraded.** The `awesome` profile makes each list entry a sourced, cross-linked page that an LLM keeps current, while `index.md` still reads as a classic awesome list.

## Contents

- [`SPEC.md`](SPEC.md): the v0.1 draft spec
- [`schemas/`](schemas/): JSON Schemas for `kb.yaml`, page frontmatter and `.openkb/kbs.yaml`
- [`examples/awesome-can-bus/`](examples/awesome-can-bus/): a small awesome-profile KB
- [`examples/project/`](examples/project/): a project that connects it

## Status

Draft. Planned next: a CLI (`openkb add | sync | index | lint`) and an MCP server that exposes connected KBs tier by tier.
