# Maintaining these notes

This KB documents the design of OpenKB. It is itself an OpenKB knowledge base, organized differently from the default layout on purpose (see `kb.yaml`).

- Background ideas go in `kb/topics/` as `type: concept`.
- Each design choice goes in `kb/decisions/` as `type: decision`: context, options considered, choice, consequences.
- Link with wikilinks (`[[progressive-context]]`). Keep `kb/README.md` listing every page with its summary.
- Log each change in `kb/CHANGELOG.md` as `## [YYYY-MM-DD] <operation> | <title>`.
