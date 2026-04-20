# agent-style sanity benchmark — task list

Ten concrete prose-writing tasks. Each task has the same prompt regardless of whether agent-style is loaded or not (baseline vs treatment). The PLAN calls for 5 PR descriptions + 3 design docs + 2 commit messages.

Tasks are written as one `<task id="..."><prompt>...</prompt></task>` block per entry so the runner can parse them mechanically without needing a YAML / JSON dependency.

## PR descriptions (5)

<task id="pr-01-redis-cache">
<prompt>
Write a 4-sentence GitHub pull-request description for a change that switches the session cache from in-process LRU to Redis. Include the rollout plan and the single biggest trade-off. Output only the PR description text, no commentary.
</prompt>
</task>

<task id="pr-02-jwt-rotation">
<prompt>
Write a 4-sentence GitHub pull-request description for a change that reduces JWT signing-key rotation from weekly to every 24 hours. Include how you handle in-flight requests during rollover. Output only the PR description text, no commentary.
</prompt>
</task>

<task id="pr-03-auth-middleware">
<prompt>
Write a 5-sentence GitHub pull-request description for a change that removes the legacy cookie-based auth middleware and makes header-based JWT the only supported scheme. Include the migration deadline for callers and the deprecation messaging. Output only the PR description text, no commentary.
</prompt>
</task>

<task id="pr-04-db-index">
<prompt>
Write a 3-sentence GitHub pull-request description for a change that adds a compound index `(user_id, created_at DESC)` to the `events` table to speed up the activity-feed query. Include the expected latency change and any lock concern during index creation. Output only the PR description text, no commentary.
</prompt>
</task>

<task id="pr-05-dependency-bump">
<prompt>
Write a 3-sentence GitHub pull-request description for a routine dependency bump: `requests` from 2.31 to 2.32.3 (security advisory GHSA-9wx4-h78v-vm56). Include the change risk assessment in one phrase. Output only the PR description text, no commentary.
</prompt>
</task>

## Design docs (3)

<task id="design-01-incident-response">
<prompt>
Write a one-paragraph (120-180 word) design-doc section titled "Incident detection". Context: the service is a payment authorization API that needs automated detection of elevated 5xx rates. Describe the detection approach, the threshold heuristic, and how alert deduplication works. Output only the section body under an H2 heading; no commentary.
</prompt>
</task>

<task id="design-02-rate-limiter">
<prompt>
Write a one-paragraph (120-180 word) design-doc section titled "Rate limiting". Context: the public REST API serves a mix of authenticated and anonymous traffic. Describe the per-IP and per-token rate limit scheme, how limits are communicated to clients, and the appeal path for developers hitting limits incorrectly. Output only the section body under an H2 heading; no commentary.
</prompt>
</task>

<task id="design-03-schema-migration">
<prompt>
Write a one-paragraph (120-180 word) design-doc section titled "Schema migration sequencing". Context: a production Postgres database with ~50M rows per table and ~3 writes/sec at peak. Describe the safe-migration order (add-nullable, backfill, add-not-null, drop-old) and explain why the sequencing matters for online deployments. Output only the section body under an H2 heading; no commentary.
</prompt>
</task>

## Commit messages (2)

<task id="commit-01-fix-timezone">
<prompt>
Write a 2-to-3-line Git commit message for a bugfix: the `/reports` endpoint was rounding timestamps to UTC before applying the user's timezone offset, causing all events near midnight to show up on the wrong day. The fix applies the offset before the rounding. First line ≤ 50 characters in imperative mood. Subsequent lines wrapped at 72. Output only the commit message, no commentary.
</prompt>
</task>

<task id="commit-02-feat-pagination">
<prompt>
Write a 2-to-3-line Git commit message for a new feature: cursor-based pagination for the `/events` list endpoint, replacing offset pagination. First line ≤ 50 characters in imperative mood. Subsequent lines wrapped at 72. Output only the commit message, no commentary.
</prompt>
</task>
