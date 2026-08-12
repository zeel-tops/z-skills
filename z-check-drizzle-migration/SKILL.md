---
name: z-check-drizzle-migration
description: >-
  Use when the user runs /z-check-drizzle-migration, after merging or rebasing a
  branch that touches drizzle migrations, when resolving conflicts in
  meta/_journal.json, before running db:migrate on a shared database, or when
  the user asks whether a migration will be skipped, is missing, or whether the
  migration folder/journal/snapshots are in a consistent state. Also applies to
  symptoms like "drizzle-kit generate refuses to run", "snapshot collision",
  "migration didn't apply", or a migration existing on disk but not in the
  journal (or vice versa).
---

# z-check-drizzle-migration

Read-only health check for drizzle migration folders. **Never modify any file
during this check** — report findings and suggest fixes; only apply fixes if
the user asks afterwards.

## Why skips happen (the core failure mode)

Drizzle's migrator applies journal entries in order but **skips any entry whose
`when` timestamp is ≤ the last-applied migration's `created_at`** in
`drizzle.__drizzle_migrations`. After a merge, a branch's migration stamped
*earlier* than one already applied is **silently skipped** — no error, missing
tables later. Journal conflicts, duplicate `idx`, and snapshot `prevId` forks
are the other recurring merge casualties.

## Steps

1. **Run the bundled checker** from the repo root (pass the user's base ref if
   they gave one, e.g. `/z-check-drizzle-migration origin/develop`):

   ```bash
   python3 ~/.claude/skills/z-check-drizzle-migration/check-drizzle-migrations.py [--base <ref>]
   ```

   It auto-discovers every migrations folder (`meta/_journal.json`), checks
   conflict markers, journal order/duplicates, missing or orphan `.sql` and
   snapshot files, snapshot `prevId` collisions, and skip risk vs the base
   branch — and vs `MERGE_HEAD` automatically when a merge is in progress.
   Exit codes: 0 clean / 1 warnings / 2 errors.

2. **Run drizzle-kit's own validation** for each drizzle config in the repo
   (e.g. `drizzle.*.config.ts`) — it is the authority on snapshot-chain health:

   ```bash
   pnpm exec drizzle-kit check --config=<config>   # or npx drizzle-kit check
   ```

   If the repo scripts define a check/generate command, prefer those. A useful
   second signal: `drizzle-kit generate` on a clean tree should report
   "No schema changes" — if it wants to create tables that already exist, the
   latest snapshot has drifted from reality.

3. **Report** a short verdict first (safe to migrate or not), then each finding
   with its concrete fix:
   - *Skip risk / out-of-order `when`* → reorder journal entries ascending by
     `when` (fix `idx` to match), or re-stamp the newer migration (rename
     `.sql` + snapshot + journal tag with a fresh timestamp) when some DB
     already applied the out-of-order entry.
   - *`prevId` collision or drifted latest snapshot* → regenerate the branch's
     snapshot: copy the migrations folder aside, drop the branch's entry from
     the copy, point a temporary drizzle config's `out` at it, run
     `drizzle-kit generate` against the merged schema, adopt only the produced
     snapshot under the existing tag, discard the rest.
   - *Missing `.sql` for a journal entry* → restore it from git history
     (`git log --all --diff-filter=A -- '**/<tag>.sql'`).
   - Lost base-branch migrations, unresolved conflict markers → resolve before
     anything else.

4. **Offer (don't auto-run) a deep verification**: apply the full chain to a
   throwaway database and assert `drizzle.__drizzle_migrations` count and order
   match the journal, then drop it. Reuse the project's own migrate helper if
   it has one (e.g. storm-predict's `migrateTenant()` from
   `src/db/provisioning/postgres-adapters.ts`). Requires a reachable database —
   ask before touching one.

## Notes

- Warnings from old hand-edited history (duplicate `idx`, data-only migrations
  without snapshots) are usually known quirks — mention them once, don't block
  on them.
- The script needs only python3 + git; safe on any repo (prints nothing
  sensitive, reads no `.env`).
