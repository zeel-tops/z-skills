---
name: z-precommit
description: >-
  Pre-commit assistant for staged git changes: clean up the staged diff (remove
  clearly-unused code it introduced and condense overly long comments, editing the
  files then reporting what changed), generate a ready-to-use Conventional Commits
  message, and warn when you're about to commit directly onto a main-like branch
  (main/master/develop/etc.) by suggesting a branch name. When invoked with the PR
  argument, write a concise pull-request description (scaled to the PR size, even a
  tiny one). Use this whenever the user runs /z-precommit, or asks for a commit
  message, a precommit check/cleanup, "what should I name this branch", or a PR
  description for the current changes — even if they don't say "z-precommit" by name.
---

# z-precommit

A pre-commit assistant. It looks at your git changes and hands back text you can
paste into `git commit`, a branch name, or a pull-request description. It is
**output-only**: it never stages, commits, branches, or pushes on its own. The
human stays in control of every git action — that's the whole point of a
pre-commit check.

There are two modes, selected by the argument passed to `/z-precommit`:

- **No argument (default):** cleanup pass + commit message + branch safety check.
- **`PR` (any casing):** pull-request description.

## Mode 1 — Commit message + branch check (default)

This is the everyday case. Run these in one batch since they're independent:

```bash
git diff --cached --stat        # what's staged, at a glance
git diff --cached               # the actual staged content
git rev-parse --abbrev-ref HEAD # current branch
git log --oneline -15           # recent history, to match scope/style conventions
```

### Step 1: Read the staged changes

Base the commit message on **staged changes only** (`git diff --cached`) — that's
what will actually be committed, and respecting that boundary is what makes this a
trustworthy pre-commit tool.

If nothing is staged, say so plainly and stop — there's nothing to commit yet.
If there are unstaged changes too, mention they exist (the user may have forgotten
to `git add`) but still summarize only what's staged.

### Step 2: Cleanup pass (edit, then show)

Before writing the message, tidy up what's about to be committed. Work **only within
the scope of the staged change** — the files and regions that appear in the diff.
Don't reformat whole files or touch code the change didn't introduce; a precommit
tool that quietly rewrites unrelated lines is worse than no tool at all.

Two things to clean:

1. **Remove clearly-unused code introduced by this change** — a variable that's
   assigned and never read, an import added but not referenced, a dead branch, a
   function defined and never called within the change. Edit the file to remove it.

   Be careful with "unused": something can look unused locally but be exported,
   referenced by name/reflection, part of a public API, or used in a file outside the
   diff. **When you're not confident it's truly dead, don't delete it — flag it
   instead** and let the human decide. Deleting something that's actually used is the
   one mistake this step must never make.

2. **Shorten verbose comments — actively, by editing the files.** Scan every comment
   the diff adds or touches and tighten it. This is not optional polish: if the diff
   contains a long comment, trimming it *is* cleanup work — do not report "nothing to
   clean" while such comments exist.
   - Any comment spanning **2+ lines** — a run of consecutive `//` lines, or a
     multi-line `/* */` / JSDoc block — that could be said in one → rewrite to a single
     concise line.
   - A wordy **single-line** comment → trim to the essential phrase.
   - Default target: **one short line per comment.** Preserve the meaning; cut the
     verbosity, the restating-of-the-code, and the hedging.

   Make the edits directly — don't merely suggest them. After editing, scan once more
   and confirm no touched comment still runs 2+ lines (other than the exceptions).

   Leave intact: public-API docstrings / contract docs callers rely on, license
   headers, and machine-read annotations (`eslint-disable`, `ts-expect-error`, type
   directives, etc.).

After editing, the working tree no longer matches the index, so **tell the user to
review the cleanup and re-stage** (`git add`) before committing — the commit message
you write next should describe the cleaned-up result. Summarize what you changed
(file:line, what was removed/trimmed) and list separately anything you only *flagged*
rather than touched.

If there's nothing to clean, say so in one line and move on — don't invent work.

### Step 3: Write the commit message

Use **Conventional Commits**: `type(scope): summary`.

- **type** — pick from what the change actually does: `feat`, `fix`, `refactor`,
  `docs`, `test`, `chore`, `perf`, `build`, `ci`, `style`.
- **scope** — optional, lowercase, the area touched (e.g. `auth`, `api`, `parser`).
  Include it when it adds clarity; omit it when the change is broad or obvious.
- **summary** — imperative mood ("add", not "added"/"adds"), lowercase start, no
  trailing period, aim for ≤ 72 characters.

Glance at `git log --oneline` first: if the repo clearly already uses a convention
(or scope vocabulary), match it rather than imposing your own — consistency in the
history matters more than your preferred flavor.

Keep it to a single line for small, focused changes. Add a short body (a blank line,
then 1–3 bullet points or sentences explaining the *why*) only when the change is
large or its motivation isn't obvious from the summary. Don't pad it.

Never add `Co-Authored-By` or any AI/attribution trailer — plain commit messages only.

**Examples:**

Input: staged changes adding JWT validation to the login handler
Output: `feat(auth): add JWT validation to login handler`

Input: staged changes fixing a crash when the user object is null
Output: `fix(api): handle null user in profile lookup`

Input: staged changes renaming variables and extracting a helper, no behavior change
Output: `refactor(parser): extract token-scanning helper`

### Step 4: Branch safety check

Find the current branch and decide whether it's a **main-like** branch — one people
generally shouldn't commit to directly: `main`, `master`, `develop`, `development`,
`trunk`, `release`, or anything starting with `release/`.

- **Not on a main-like branch:** good — just note the current branch is fine to
  commit to.
- **On a main-like branch:** warn the user, and suggest a new branch to create first.
  Use `type/kebab-summary` derived from the commit you just wrote — the same type,
  and a short kebab-case slug of the summary. Provide the exact command so it's
  one copy-paste:

  ```
  feat(auth): add JWT validation to login handler
  → you're on `main`. Create a branch first:
      git switch -c feat/jwt-validation-login
  ```

### Output format for Mode 1

Keep it tight and copy-paste friendly:

```
Cleanup:
  <what you edited (file:line — removed/trimmed), OR "Nothing to clean.">
  Flagged (not changed): <anything uncertain you left for the user, if any>
  → review and `git add` the cleaned files before committing.   (only if you edited)

Commit message:
  <type(scope): summary>
  [optional body]

Branch: <current-branch>
  <"OK to commit here." OR the warning + suggested `git switch -c ...` command>
```

## Mode 2 — PR description (`/z-precommit PR`)

Triggered when the argument is `PR` (case-insensitive). Here the unit of interest is
the whole branch, not a single staged diff — a PR bundles every commit since the
branch diverged from its base.

### Step 1: Find the base branch and the branch's changes

Determine the base (default) branch, then read everything the branch adds on top of it:

```bash
# Find the repo's default branch (falls back to main/master if origin/HEAD is unset)
git symbolic-ref --quiet --short refs/remotes/origin/HEAD
git rev-parse --abbrev-ref HEAD          # current branch
git log <base>..HEAD --oneline           # commits that will be in the PR
git diff <base>...HEAD --stat            # files changed
git diff <base>...HEAD                   # full diff for the PR
```

If `origin/HEAD` isn't set, fall back to whichever of `main` or `master` exists. If
the current branch *is* the base branch, there's nothing to compare — tell the user
they need to be on a feature branch.

### Step 2: Write the PR description

Format: **title + summary + bullets** — but scale it to the actual size of the PR.
A description should be proportional to the change; padding a tiny PR with bullets
that just restate the title wastes a reviewer's time.

- **Title** — one line, imperative, like a good commit summary. A Conventional
  Commits prefix is fine if the repo uses them.
- **Summary** — 1–2 sentences on *what this PR does and why*. Focus on intent and
  impact, not a file-by-file walkthrough.
- **Key changes** — a few bullets covering the substantive changes a reviewer cares
  about. Group related edits; skip noise.

**Small PRs (a single commit or a handful of changed lines):** don't force the full
shape. A title plus one or two sentences is usually enough — and if the title already
says it all, even the summary can be a single sentence. Add a bullet list only when
there's genuinely more than one distinct change worth calling out. The "Key changes"
bullets are optional, not mandatory.

Keep it short and on-point. **Do not** include sections about test cases, testing
steps, test plans, screenshots, checklists, or boilerplate headers — the user
specifically doesn't want that filler. Describe the change itself.

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

Output just the PR description (title, summary, bullets) in a single block the user
can paste straight into the PR. Don't wrap it in extra commentary.
