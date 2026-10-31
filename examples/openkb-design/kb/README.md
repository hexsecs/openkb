# OpenKB design notes

## Topics

- [[topics/llm-wiki|LLM Wiki pattern]] — An LLM incrementally compiles raw sources into a persistent, interlinked Markdown wiki that it keeps current.
- [[topics/progressive-context|Progressive context]] — Load knowledge in tiers, from a one-line description down to raw sources, only as deep as a task needs.

## Decisions

- [[decisions/manifest-declares-layout|The manifest declares the layout]] — KBs can be organized freely because consumers find everything through paths declared in kb.yaml.
