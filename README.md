# OpenKB

An open standard for **LLM-maintained knowledge bases** ("LLM wikis") that projects can connect and load in stages.

- **One format.** Every KB has a manifest (`kb.yaml`), an index (`index.md`) and wiki pages with frontmatter, so any agent or tool can read any KB.
- **Progressive context.** Each KB offers four tiers: a one-line description (L0), an index (L1), pages (L2) and raw sources (L3). Agents load only as deep as the task needs, so a project can connect many KBs cheaply.
- **Connect many KBs to a project.** List them in `.openkb/kbs.yaml`; tooling turns that into a short `context.md` the project's agent always sees.
- **Awesome lists, upgraded.** The `awesome` profile makes each list entry a sourced, cross-linked page that an LLM keeps current, while `index.md` still reads as a classic awesome list.

## Contents

- [`SPEC.md`](SPEC.md): the v0.1 draft spec
- [`schemas/`](schemas/): JSON Schemas for `kb.yaml`, page frontmatter and `.openkb/kbs.yaml`
- [`examples/awesome-can-bus/`](examples/awesome-can-bus/): a small awesome-profile KB
- [`examples/project/`](examples/project/): a project that connects it

## Status

Draft. Planned next: a CLI (`openkb add | sync | index | lint`) and an MCP server that exposes connected KBs tier by tier.
