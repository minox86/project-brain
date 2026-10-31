---
product: null
glossary_languages: [en, it]
archive_after_days: 90
open_question_stale_days: 30
digest_retention_days: 30
context_pack_max_words: 4000
raw_max_words: 3000
---
# Brain settings

- `product`: name of the product this brain describes.
- `glossary_languages`: languages of the glossary; `concept` pages carry `term_<lang>` for each.
- `archive_after_days`: superseded decisions and closed open questions not updated for this long are left out of `index.md`.
- `open_question_stale_days`: open questions not updated for this long are flagged by `pb lint`.
- `digest_retention_days`: routine digests older than this are deleted by `pb generate` (history stays in git).
- `context_pack_max_words`: hard cap of a context pack; beyond it pages are included as summaries.
- `raw_max_words`: extracted text longer than this is not stored in `raw/`; a summary with the external link is kept instead.
