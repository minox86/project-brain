# {{product}} brain

Product knowledge base for humans and AI agents, maintained with the `pb` (project-brain) Claude plugin.

- Start here: [`index.md`](index.md) · [`glossary.md`](glossary.md) · [`features.md`](features.md) · rules in [`AGENTS.md`](AGENTS.md)
- `functional/` features and concepts · `technical/` modules, interfaces, environments · `epics/` Jira epics in progress · `decisions/` · `open-questions/`
- `digests/` what the scheduled routine ingested · `raw/` text extracted from uploaded files

Pages change in working branches, with the code, and reach the default branch with its PR; the scheduled routine writes on `docs/brain` and its PR "Brain updates" is brought in with `/pb:merge`. Generated files (`index.md`, `glossary.md`, `features.md`, `context/`) are refreshed by every save; never edit them by hand.
