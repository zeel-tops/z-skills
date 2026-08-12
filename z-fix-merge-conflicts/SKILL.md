---
name: z-fix-merge-conflicts
description: >-
  Use when the user runs /z-fix-merge-conflicts, or has merge conflicts after a
  pull, merge, rebase, or cherry-pick and wants them resolved without losing
  either side's work. Also applies to phrasings like "fix the conflicts",
  "resolve conflicts after pulling dev", "I rebased and everything broke",
  "which side should I keep", or symptoms like conflict markers (<<<<<<<) left
  in files, a half-merged branch, or code that merged cleanly but broke because
  one branch renamed something another branch still calls.
---

# z-fix-merge-conflicts

Resolve an in-progress merge / rebase / cherry-pick **without breaking either
side's functionality** — the old flow and the new flow must both still work
when this is done.

Then explain, in plain language, what each side had, why it clashed, and what
was kept.

## Core principle

**A conflict is not a formatting problem to clear — it is two working features
arriving at the same lines.** The default answer is almost always *keep both*.
Taking one side wholesale silently deletes shipped work, and that deletion has
no marker, no error, and no test to catch it.

When you genuinely cannot tell which side is right, **stop and ask**. A wrong
guess is far more expensive than a question.

## Step 1 — Find out where you are

```bash
python3 ~/.claude/skills/z-fix-merge-conflicts/analyze-conflicts.py
```

This prints the operation in progress, which branch is which, every conflicted
file, and — per file — **what each side changed relative to their shared
starting point**. It also writes each file's three versions into
`.git/z-conflict-analysis/` so you can read them in full. It modifies nothing
in the working tree.

Use `--file <path>` to focus on one file and `--json` for structured output.

**Get the sides right before reading a single line of code.** In a merge,
stage 2 (`ours`) is the user's branch. **In a rebase this is reversed** —
stage 2 is the upstream branch being replayed onto, and stage 3 (`theirs`) is
the user's own commits. The script resolves this and labels the two sides
"YOUR side" and "INCOMING side"; use those labels throughout and never say
ours/theirs to the user.

If nothing is in progress, say so and stop.

## Step 2 — Understand each conflict before touching it

For every conflicted file:

1. Read the **YOUR side** and **INCOMING side** diffs from the script. These
   are diffs against the common starting point, which is what actually reveals
   what is new on each branch — reading the two final versions side by side
   does not.
2. Read the surrounding code in the working-tree file for real context.
3. If intent is unclear, look at the commits behind each side:
   ```bash
   git log --merge --oneline -- <file>       # commits from both sides
   git log -p --merge -- <file>              # with their diffs
   ```
4. Decide what each side was *trying to achieve*. You are merging intentions,
   not text.

## Step 3 — Sort each conflict into a bucket

| Bucket | Looks like | Action |
|---|---|---|
| **Additive, no overlap** | both added a different i18n key, import, route, test, or enum member | **Keep both.** Order them sensibly. |
| **Same lines, compatible** | one added `.where(...)`, the other added `.orderBy(...)` | **Combine both.** Neither feature is lost. |
| **One side rewrote what the other tweaked** | they refactored a function; you renamed a variable inside it | **Take the rewrite, then re-apply the other side's intent on top.** |
| **A real either/or choice** | two different UI layouts, two different business rules, two different validation limits | ⏸️ **Leave it alone. Ask.** |

Escalate to ⏸️ **ask** whenever any of these are true:

- Resolving requires writing **new** code rather than joining the two sides
- The two sides encode contradictory business rules or product decisions
- Either side touches auth, RBAC guards, tenant scoping, audit logging,
  encryption, or anything else security- or compliance-relevant, and the
  correct combination is not obvious
- One side deleted something the other side changed
- The file is binary, or a lock file where neither side is clearly newer

### Files with their own rules

The script flags these; follow the flag.

- **Drizzle `_journal.json` / snapshots / migration SQL** — never drop a
  migration. Keep both, renumber `idx`, and bump the later `when` so ordering
  is real. Verified in Step 6.
- **Lock files** (`pnpm-lock.yaml`, etc.) — never hand-merge. Take one side and
  regenerate with the repo's install command from the repo root.
- **i18n locale JSON** — keep both sets of keys, then check the mirror locale
  (`en` ↔ `fr`) has the matching pair for every key kept.
- **Generated / built output** — resolve the source, then regenerate.

## Step 4 — Fix the clear ones

Edit the working-tree file directly and remove the conflict markers only for
conflicts you resolved deliberately.

**Never do any of these:**

- ❌ `git checkout --ours/--theirs <file>` or accepting one whole side just to
  make markers disappear
- ❌ `git merge --abort`, `git rebase --abort`, `git reset --hard` — destructive
  and never yours to run unprompted
- ❌ Deleting an i18n key, a migration, a test, an audit-log call, a tenant
  scope, an RBAC guard, or a validation rule to make a conflict go away
- ❌ Resolving a file you are unsure about "provisionally"

**Leave every ⏸️ file exactly as it is, markers intact.** Git still counts it
as unresolved, so a half-finished merge cannot be committed by accident.

## Step 5 — Check everything that uses the fixed code

This is where merges actually break, and it is not optional.

**The file that breaks usually never conflicted.** If one branch renames
`formatStormDate` and another adds a new call to the old name in a different
file, git merges both cleanly, produces zero conflicts, and ships broken code.
Only a deliberate sweep finds it.

For each file you resolved:

1. **List what changed on the outside** — exported function names and
   signatures, return shapes, exported types/interfaces, component props, DTO
   fields, schema column names, route paths, query keys, i18n keys, constants.
2. **Find every user of those things.** Grep the repo for each symbol, not just
   for imports of the file — re-exports through an `index.ts` hide the direct
   import.
3. **Check each user** for: wrong argument count or types, a field that was
   renamed or removed, a prop that became required, a service calling a
   repository method that no longer exists, a `t('...')` key that one side
   deleted.
4. **Sweep for silent breaks.** For every symbol either side **removed or
   renamed**, grep the whole repo for the old name. Any remaining hit is a
   break in a file that never conflicted.
5. **Check the other direction too** — did the incoming side change something
   your resolved file depends on?

**How far to follow the chain:** check every direct user. If a direct user just
consumes the change internally and its own exported shape is unchanged, stop
there. If it passes the changed thing onward or re-exports it, keep following.

Fix mismatches you are confident about. Anything ambiguous joins the ⏸️ list.

## Step 6 — Verify

Run these in order, and report the real output. Never claim a check passed
without having run it.

1. **No leftover markers** in any file you touched:
   ```bash
   git diff --name-only --diff-filter=U   # what git still calls unresolved
   grep -rnE '^(<{7}|={7}|>{7})' <each file you resolved>
   ```
   Files you deliberately left for the user *should* still show markers —
   everything else must be clean.

2. **Typecheck the affected workspace(s).** Use the repo's own script (check
   `package.json` / `CLAUDE.md`); fall back to `npx tsc --noEmit -p <path>`.
   Only workspaces that had conflicts or affected files.

3. **Targeted tests only** — for the conflicted files **and** the affected
   files from Step 5. Never the full suite unless the user asks.
   ```bash
   # jest
   pnpm --filter <workspace> test -- --findRelatedTests <files...>
   ```

4. **Drizzle check**, if anything under a `drizzle/` folder was touched — run
   the `z-check-drizzle-migration` skill to confirm no migration is skipped,
   duplicated, or orphaned.

## Step 7 — Report

Print this in chat. Do not write it to a file.

````markdown
# 🔀 Merge conflict fix — summary

**You are on:** <your branch>
**You pulled in:** <incoming branch>   *(rebase: say so — the sides are swapped)*
**Conflicted files:** N → **X fixed**, **Y waiting on your answer**

### Quick view

| # | File | What clashed | What I did |
|---|---|---|---|
| 1 | path/to/file.ts | one-line plain-English reason | Combined both |

---

## 1. path/to/file.ts

**Before — your branch (`<branch>`) had:**
```ts
<the real code from your side>
```
> Plain meaning: <one line, no jargon>

**Before — the pull (`<branch>`) had:**
```ts
<the real code from the incoming side>
```
> Plain meaning: <one line, no jargon>

**Why it clashed:** <one or two plain sentences>

**After — what I kept:**
```ts
<the resolved code>
```
> Plain meaning: <one line — say explicitly what was kept from each side>

**Nothing broken:** <why both features still work>

---

## 🔗 Other files affected by these fixes

| File | What it uses | Status |
|---|---|---|
| users.service.ts | calls findActiveUsers() | ✅ Fine — arguments unchanged |
| users.controller.ts | reads user.scopeIds | 🔧 Fixed — renamed to locationScopeIds (2 places) |
| EventList.tsx | calls formatStormDate() | ⚠️ Silent break — never conflicted, but the pull deleted this function |

Every 🔧 and ⚠️ row gets the same before / before / after treatment as above.

---

## ⏸️ Needs your decision — left untouched

**File:** path/to/file.tsx — conflict markers are **still in the file**.

**Your branch:** <what it does>
**The pull:** <what it does>
**Why I stopped:** <the real reason it is not mechanical>

- **A —** <option> <why>
- **B —** <option> <why>

**My suggestion:** <A or B, and why>

---

## ✅ Checks I ran
<the actual commands and their actual results>

## 🚫 Not done
- **Nothing committed.** The <merge/rebase> is still in progress.
````

**Write every explanation in simple, direct language.** No "resolved the
divergent hunks" — say "both branches changed the same lines, so I kept both
changes."

## Step 8 — Stop

**Do not run `git add`, `git commit`, `git merge --continue`, or
`git rebase --continue`.** Present the summary and stop.

After the user answers the ⏸️ items: apply those resolutions, re-run Step 5 and
Step 6 for just those files and their users, and print a short follow-up
summary covering only what changed. Then stop again and ask before committing.

Clean up `.git/z-conflict-analysis/` once the user confirms they are done with
the summary.
