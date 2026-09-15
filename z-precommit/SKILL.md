---
name: z-precommit
description: Pre-commit check for staged changes — cleans the staged diff, writes a Conventional Commits message, and warns before committing to a main-like branch. Pass PR for a quick pull-request description instead.
argument-hint: "[PR]"
disable-model-invocation: true
---

# z-precommit

A pre-commit assistant. It looks at your git changes and hands back text you can paste into
`git commit`, a branch name, or a pull-request description.

**It never runs git commands that change state** — no staging, committing, branching, pushing.
The human owns every git action; that's the whole point of a pre-commit check. The only thing it
touches is file content during the cleanup pass, and it reports exactly what it changed.

## 0. Read the argument

- No argument → **Mode 1**: cleanup + commit message + branch safety check.
- `PR` (any casing) → **Mode 2**: pull-request description.
- Anything else → say it's not a recognised mode, name the two valid ones, and stop. Don't fall
  into Mode 1 on a typo like `RP`.

In either mode, if HEAD is detached (`git rev-parse --abbrev-ref HEAD` prints `HEAD`), say so and
stop — commit messages and branch checks assume you're on a branch.

## Mode 1 — Commit message + branch check (default)

This is the everyday case. Run these in one batch since they're independent:

```bash
git diff --cached --stat        # what's staged, at a glance
git diff --cached               # the actual staged content
git diff --name-only            # unstaged changes — feeds the partial-staging guard
git rev-parse --abbrev-ref HEAD # current branch
git log --oneline -15           # recent history, to match scope/style conventions
```

### Step 1: Read the staged changes

Base the commit message on **staged changes only** (`git diff --cached`) — that's what will
actually be committed, and respecting that boundary is what makes this a trustworthy pre-commit
tool.

If nothing is staged, say so plainly and stop — there's nothing to commit yet. If there are
unstaged changes too, mention they exist (the user may have forgotten to `git add`) but still
summarize only what's staged.

### Step 2: Cleanup pass (edit, then show)

Before writing the message, tidy up what's about to be committed. Work **only within the scope of
the staged change** — the files and regions that appear in the staged diff. Don't reformat whole
files or touch code the change didn't introduce; a precommit tool that quietly rewrites unrelated
lines is worse than no tool at all.

**Partial-staging guard — run this before editing anything:**

```bash
comm -12 <(git diff --name-only | sort) <(git diff --cached --name-only | sort)
```

Every file it prints has BOTH staged and unstaged changes. **Flag those — never edit them.**
Re-staging such a file with `git add` would sweep the user's deliberately-unstaged hunks into the
commit. Tell them what you would have cleaned, and that `git add -p` is the safe way to stage the
cleanup if they want it.

Also skip entirely: lock files, generated/built output, and binaries — nothing to hand-clean
there.

**Scale:** past roughly 500 staged lines, clean only the files with substantive changes and name
the files you skipped — don't silently truncate the pass.

Two things to clean:

1. **Remove clearly-unused code introduced by this change** — a variable that's assigned and
   never read, an import added but not referenced, a dead branch, a function defined and never
   called within the change. Edit the file to remove it.

   Be careful with "unused": something can look unused locally but be exported, referenced by
   name/reflection, part of a public API, or used in a file outside the diff. **When you're not
   confident it's truly dead, don't delete it — flag it instead** and let the human decide.
   Deleting something that's actually used is the one mistake this step must never make.

2. **Shorten verbose comments — actively, by editing the files.** Scan every comment the diff
   adds or touches and tighten it. This is not optional polish: if the diff contains a long
   comment, trimming it *is* cleanup work — do not report "nothing to clean" while such comments
   exist.
   - Any comment spanning **2+ lines** — a run of consecutive `//` lines, or a multi-line
     `/* */` / JSDoc block — that could be said in one → rewrite to a single concise line.
   - A wordy **single-line** comment → trim to the essential phrase.
   - Default target: **one short line per comment.** Preserve the meaning; cut the verbosity,
     the restating-of-the-code, and the hedging.

   Make the edits directly — don't merely suggest them. After editing, scan once more and confirm
   no touched comment still runs 2+ lines (other than the exceptions).

   Leave intact: public-API docstrings / contract docs callers rely on, license headers, and
   machine-read annotations (`eslint-disable`, `ts-expect-error`, type directives, etc.).

After editing, the working tree no longer matches the index, so **tell the user to review the
cleanup and re-stage** (`git add`) before committing — the commit message you write next should
describe the cleaned-up result.

If there's nothing to clean, say so in one line and move on — don't invent work.

### Step 3: Write the commit message

Use **Conventional Commits**: `type(scope): summary`.

- **type** — pick from what the change actually does: `feat`, `fix`, `refactor`, `docs`, `test`,
  `chore`, `perf`, `build`, `ci`, `style`.
- **scope** — optional, lowercase, the area touched (e.g. `auth`, `api`, `parser`). Include it
  when it adds clarity; omit it when the change is broad or obvious.
- **summary** — imperative mood ("add", not "added"/"adds"), lowercase start, no trailing period,
  aim for ≤ 72 characters.

Glance at `git log --oneline` first: if the repo clearly already uses a convention (or scope
vocabulary), match it rather than imposing your own — consistency in the history matters more
than your preferred flavor.

Keep it to a single line for small, focused changes. Add a short body (a blank line, then 1–3
bullet points or sentences explaining the *why*) only when the change is large or its motivation
isn't obvious from the summary. Don't pad it.

Never add `Co-Authored-By` or any AI/attribution trailer — plain commit messages only.

**Examples:**

Input: staged changes adding JWT validation to the login handler
Output: `feat(auth): add JWT validation to login handler`

Input: staged changes fixing a crash when the user object is null
Output: `fix(api): handle null user in profile lookup`

Input: staged changes renaming variables and extracting a helper, no behavior change
Output: `refactor(parser): extract token-scanning helper`

### Step 4: Branch safety check

Decide whether the current branch is **main-like** — one people generally shouldn't commit to
directly: `main`, `master`, `develop`, `development`, `trunk`, `release`, or anything starting
with `release/`.

- **Not main-like:** good — the Branch line in the output just confirms it.
- **Main-like:** warn, and suggest a new branch to create first. Use `type/kebab-summary` derived
  from the commit you just wrote — the same type, and a short kebab-case slug of the summary —
  and give the exact command so it's one copy-paste.

### Output format for Mode 1

Chat only. Drop any line that doesn't apply — no empty sections, no filler.

````markdown
## ✅ Pre-commit check

**Cleanup**
- `auth/login.ts:42` — removed unused `retryCount` variable
- `auth/login.ts:18` — 4-line comment → 1 line
- ⏸️ Flagged, not touched: `utils/index.ts:7` — export looks unused but may be public API
- ⏸️ Partially staged, not touched: `api/client.ts` — re-staging would sweep your unstaged hunks
  (stage the cleanup with `git add -p` if you want it)

→ Review and re-stage (`git add`) the cleaned files before committing.

**Commit message**
```
feat(auth): add JWT validation to login handler
```

**Branch:** `feature/jwt-auth` — ✅ OK to commit here.
````

- With nothing to clean, the Cleanup section is the single line `Nothing to clean.` and the
  re-stage arrow line disappears.
- The commit message always sits alone in its own fenced block — it's the copy-paste payload.
  A body, when needed, goes inside the same block after a blank line.
- On a main-like branch the Branch line becomes:

  ````markdown
  **Branch:** `main` — ⚠️ main-like branch. Create one first:
  ```
  git switch -c feat/jwt-validation-login
  ```
  ````

## Mode 2 — PR description (`/z-precommit PR`)

> The quick, paste-able description. For a rich, file-based description with flow diagrams and a
> local-run guide, use `/z-pr-description` instead.

Here the unit of interest is the whole branch, not a single staged diff — a PR bundles every
commit since the branch diverged from its base.

### Step 1: Find the base branch and the branch's changes

```bash
# Find the repo's default branch
git symbolic-ref --quiet --short refs/remotes/origin/HEAD   # e.g. origin/main
git rev-parse --abbrev-ref HEAD           # current branch
git log origin/<base>..HEAD --oneline     # commits that will be in the PR
git diff origin/<base>...HEAD --stat      # files changed
git diff origin/<base>...HEAD             # full diff for the PR
```

- If `origin/HEAD` isn't set, fall back to whichever of `main`, `master`, or `develop` exists.
- **Prefer the remote ref (`origin/<base>`) over the local one** — a stale local base overstates
  the diff with already-merged work. If only a local ref exists, use it and say so.
- If the current branch *is* the base branch, there's nothing to compare — tell the user they
  need to be on a feature branch, and stop.

### Step 2: Write the PR description

Format: **title + summary + bullets** — but scale it to the actual size of the PR. A description
should be proportional to the change; padding a tiny PR with bullets that just restate the title
wastes a reviewer's time.

- **Title** — one line, imperative, like a good commit summary. A Conventional Commits prefix is
  fine if the repo uses them.
- **Summary** — 1–2 sentences on *what this PR does and why*. Focus on intent and impact, not a
  file-by-file walkthrough.
- **Key changes** — a few bullets covering the substantive changes a reviewer cares about. Group
  related edits; skip noise.

**Small PRs (a single commit or a handful of changed lines):** don't force the full shape. A
title plus one or two sentences is usually enough — and if the title already says it all, even
the summary can be a single sentence. Add a bullet list only when there's genuinely more than one
distinct change worth calling out. The "Key changes" bullets are optional, not mandatory.

Keep it short and on-point. **Do not** include sections about test cases, testing steps, test
plans, screenshots, checklists, or boilerplate headers — the user specifically doesn't want that
filler. Describe the change itself.

**Example (larger PR):**

```
Add JWT-based authentication to the login flow

Replaces the session-cookie login with stateless JWT auth so the API can scale
horizontally without sticky sessions. Tokens are signed server-side and validated
on each request.

Key changes:
- Add `issueToken` / `verifyToken` helpers in `auth/jwt.ts`
- Swap the cookie middleware for JWT validation on protected routes
- Return the token from `POST /login` and document the new header contract
```

**Example (small PR — one focused change):**

```
Fix off-by-one in pagination offset

The page offset was computed as `page * size` instead of `(page - 1) * size`,
so the first page was skipped. Corrected the calculation in `paginate()`.
```

### Output format for Mode 2

Output just the PR description in **one fenced block** the user can copy straight into the PR —
no commentary before or after it.
