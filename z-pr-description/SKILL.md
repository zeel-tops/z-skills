---
name: z-pr-description
description: >-
  Generate a rich, structured pull-request description and write it to a separate
  markdown file (default PR_DESCRIPTION.md at the repo root). Reproduces a fixed,
  informative format: title + summary, Jira ticket links, a "how it works" flow
  section with a Mermaid sequence/flow diagram and numbered step-by-step, any
  relevant mapping tables, a grouped "What's in this PR" (Backend / Frontend /
  Tests & docs), and a "Try it out locally" section with install + migration + run
  + which page/route to open. It inspects the branch diff vs the base branch to fill
  this in, and ASKS the user for anything it cannot determine — especially the Jira
  ticket link(s), the base branch if ambiguous, and the page/route to open. It is
  output-only: it never stages, commits, branches, or pushes. Use whenever the user
  runs /z-pr-description, or asks for a PR/MR description written to a file for the
  current branch.
---

# z-pr-description

Produce a **detailed, well-structured PR description** and save it to its own
markdown file — the same format as a hand-crafted feature PR: title, Jira links,
an explained flow with a Mermaid diagram and numbered steps, a grouped change list,
and a "try it out" runbook.

This skill is **output-only**: it inspects git and the code, writes a markdown file,
and reports. It never stages, commits, branches, or pushes — the human owns every git
action.

**Golden rule:** when you don't know something the description needs, **ask the user**
rather than guessing or inventing it. The most common unknown is the Jira ticket
link(s) — always ask if you can't find them.

## Step 1 — Scope the PR against the base branch

Run these (independent — batch them):

```bash
# Resolve the base/default branch (prefer the remote's HEAD; fall back to main/master)
git symbolic-ref --quiet --short refs/remotes/origin/HEAD   # e.g. origin/main
git rev-parse --abbrev-ref HEAD                             # current branch

# Prefer origin/<base> over a local base ref — the local one is often STALE and will
# overstate the diff with already-merged work.
git log origin/<base>..HEAD --oneline                      # commits in the PR
git diff origin/<base>...HEAD --stat                       # size + files
git diff origin/<base>...HEAD --name-only                  # full file list
git diff origin/<base>...HEAD                              # the actual changes
```

Notes:
- If `origin/<base>` doesn't exist, fall back to local `main`/`master`, but **say so**.
- If the local base ref looks far behind the remote (the diff includes obviously
  already-merged foundation work), scope against `origin/<base>` and mention that you did.
- If the current branch **is** the base branch, stop — there's nothing to compare; tell
  the user to switch to a feature branch.
- Read the actual diff well enough to describe the *flow*, not just list files.

## Step 2 — Gather what you can't see in the diff (ASK when unknown)

Before writing, make sure you have:

1. **Jira ticket link(s)** — REQUIRED if the team uses them. Try to infer from the branch
   name or commit messages (e.g. `SS-57`, `PROJ-123`). If you can't find a ticket ID/URL,
   **ask the user for the link(s)** — don't omit the section and don't fabricate IDs.
2. **Base branch** — if ambiguous, confirm with the user.
3. **The page/route to open** — for a UI change, identify the route (e.g. `/users`) from the
   diff (router files). If you can't tell, ask.
4. **Output file path** — default `PR_DESCRIPTION.md` at the repo root. If one already
   exists, ask whether to overwrite or write to a new path (e.g. `docs/pr/<branch>.md`).

Ask these as concise questions (group them). Don't block on questions you can answer from
the diff yourself.

## Step 3 — Detect the "try it out" mechanics from the repo

So the runbook is accurate, detect (don't assume):
- **Package manager / monorepo:** look for `pnpm-workspace.yaml` / `pnpm-lock.yaml`
  (pnpm), `yarn.lock`, or `package-lock.json`; and the dev script (`pnpm dev`, etc.).
- **Migrations:** did the diff add/change migration files or schema (e.g. anything under a
  `drizzle/`, `migrations/`, `prisma/` folder, or `*.sql`)? If so, the runbook MUST include
  the migration step. Find the **apply** command in `package.json` scripts / README —
  distinguish "generate migration files" from "apply them" (e.g. in this repo
  `db:generate:*` only generates; `pnpm --filter server db:bootstrap` applies + seeds).
  When unsure which script applies migrations, check the README; if still unclear, ask.
- **Run command + URL:** the dev server command and the dev URL/port (and tenant subdomain
  if the app is subdomain-routed).

## Step 4 — Write the file in THIS structure

Scale each section to the PR, but keep this skeleton. Use real values from the diff.

````markdown
# <type>: <concise feature summary>

<1–3 sentence summary: what this PR delivers and the key design idea/why.>

**Jira tickets:**
- [<TICKET-ID>](<url>)
- [<TICKET-ID>](<url>)

## <The core idea / key concept>        ← include only when there's a non-obvious design
<Short explanation of the central concept (e.g. two data stores and the link between
them), ideally with a small table. Skip for simple PRs.>

## How it works / Flow

<For each significant flow (often one per endpoint/user action), give:
 a Mermaid diagram THEN a numbered step-by-step walkthrough including error/rollback paths.>

### Flow 1 — <name> (`<METHOD> <route>`)

```mermaid
sequenceDiagram
  participant ...
  ... derive the real participants and calls from the code ...
  alt <failure case>
    ... rollback / error path ...
  else success
    ...
  end
```

Step by step:
1. **<step>** — <what + why>.
2. ...

<Add Flow 2, mapping/status tables, etc. when the feature has them.>

## What's in this PR

**Backend**
- <grouped, substantive bullets — modules/responsibilities, not a file-by-file dump>

**Frontend**
- <grouped bullets>

**Tests & docs**
- <coverage added; any docs added>

## Try it out locally

<One line on why a setup step is needed if migrations/deps changed.>

```bash
# 1. Get the latest code
git checkout <base> && git pull
git checkout <branch>

# 2. Install deps (if the lockfile changed)
<install cmd>

# 3. Run migrations   ← include ONLY if schema/migrations changed; use the APPLY cmd
<migration apply cmd>

# 4. Start the app
<dev cmd>
```

Then open **<feature screen>** at **`<url/route>`** to see it.

> <One-time prerequisites (hosts/env), and any external dependency (e.g. cloud creds)
>  needed for the full flow — note what still works without them.>

## Notes for reviewers        ← optional; include real caveats only
- <honest limitations / known gaps / follow-ups>
````

### Content rules
- **Diagrams must reflect the real code** — derive participants and call order from the
  actual controller/service/etc. in the diff. Don't draw a generic diagram.
- **Group, don't dump** — "What's in this PR" bullets describe responsibilities and
  behavior, not every file.
- **No filler** — do NOT add test-plan/checklist/screenshot/"how to test" boilerplate
  sections. (A factual "Tests & docs" bullet listing what coverage was added is fine.)
- **Be honest in "Notes for reviewers"** — surface real gaps (e.g. assumptions, unwired
  pieces, single-page limits), don't oversell.
- Match the repo's existing PR/commit conventions (Conventional Commits prefix if used).

## Step 5 — Report

After writing the file, tell the user:
- The output path.
- The PR scope you used (base branch, commit count, file/line stats) and if you scoped
  against `origin/<base>` because local was stale.
- Anything you asked about or assumed (tickets, route, migration command).
- A reminder that nothing was staged/committed — it's a working-tree file to paste.

Offer to adjust depth or rescope if their MR targets a different base.
