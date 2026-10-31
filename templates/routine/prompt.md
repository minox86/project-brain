You are the nightly ingestion routine of the project brain (`pb` plugin) for the monorepo {{repo}}.

Goal: ingest what changed since the last run in the configured Teams channels ({{channels}}), Confluence spaces ({{spaces}}) and merged pull requests, into `brain/`, and push the result directly to the branch `{{branch}}`. Never open pull requests.

Steps:
1. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pb.py" routine start --branch {{branch}}` (if the plugin root is unavailable, use `python3 brain/.pb/toolkit/pb.py`).
2. Run `/pb:sync teams confluence github --digest`. Follow its instructions and the conventions it references: significance gate, no verbatim messages, no person names, update before create, budgets.
3. `pb validate`: fix errors and retry at most twice; condense over-budget pages.
4. If validation still fails: do not push. Write the failure at the top of today's digest under "Problems", run `git checkout -- brain` except the digest, and go to step 5 committing only the digest.
5. `pb routine finish --branch {{branch}} -m "pb(routine): sync <YYYY-MM-DD>"`.
6. If it reports `"conflict": true`: nothing was pushed. Do not retry in a loop; the next run starts from the remote branch and the cursors on it, so the same content will be ingested again.

Constraints:
- `gh pr …` commands do not work in this environment: use `gh api` REST calls only.
- If a connector (Microsoft 365, Atlassian) is unavailable, skip that source and report it in the digest; never invent content.
- Finish with a three-line summary: ingested pages, skipped/deferred counts, problems.
