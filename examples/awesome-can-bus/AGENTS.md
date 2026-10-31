# Maintaining this KB

This is an OpenKB knowledge base (profile `awesome`). Follow `SPEC.md` v0.1.

## ingest <url or text>
1. If an entry for the thing already exists, update it; otherwise create `wiki/<id>.md` with `kind: entry`.
2. Fill `summary` (≤ 160 chars), `category`, `url`, `status`, `last_checked`, and cite every claim in `sources`.
3. Add `related` links both ways to entries it compares with or works alongside.
4. Regenerate `index.md` from frontmatter, grouped by `category`, topics last.
5. Append a line to `log.md`.

## lint
Check frontmatter against the schemas, broken links, orphan pages, entries whose `last_checked` is older than 90 days, and pages over 2,000 tokens. Report and fix, then append to `log.md`.

## Rules
- Never invent facts, versions or licenses. If a source doesn't say it, leave the field out.
- Keep pages short; split rather than grow past the budget.
