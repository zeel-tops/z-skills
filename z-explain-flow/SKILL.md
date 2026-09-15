---
name: z-explain-flow
description: Trace a ticket's implemented flow end to end — click → route → endpoint → service → query → tables — with the real API endpoints, an input/output example, and what's built vs. still open. Explanation only; never changes code or writes files.
argument-hint: "<ticket-id>"
disable-model-invocation: true
---

# Explain the flow

**What you produce:** a step-by-step walkthrough of how one ticket's feature **actually works in
this codebase right now** — every hop from the user's click to the database and back, the tables
it reads, the endpoints it exposes, a real request/response example, and an honest status of what
is built versus still open. Printed **in chat only** — never written to a file.

This is the deep technical companion to `z-simplify-ticket`. That one answers *"what is this
ticket about?"* in plain English. This one answers *"how does the code actually work?"* — and it
is worthless unless every claim comes from a file you opened.

## 0. Read the argument

- A bare ID (`SS-783`, `proj-123`, case-insensitive) → uppercase it and use it.
- A full Jira URL (`https://…/browse/SS-783`) → extract the key from the URL.
- Several IDs → trace each in turn, same format, separated by a `---` rule.
- **No ticket at all** — a feature name, a route, an endpoint (`"the scenario detail page"`,
  `"GET /events/:id/runs"`) → skip step 1 and trace it the same way, with an "What this is"
  section written from the code instead of the ticket.
- Nothing usable → ask what to trace and stop. Don't guess from branch names or recent chat.

## 1. Fetch the ticket

Load the Atlassian tools first — they are deferred:
`ToolSearch` → `select:mcp__atlassian__getJiraIssue,mcp__atlassian__getAccessibleAtlassianResources`
If those exact names don't exist, ToolSearch for `jira` and use the closest get-issue tool.

- Read the **summary, description, acceptance criteria, and comments.** Request the `comment`
  field explicitly — the real requirement is often three comments down, not in the description.
- **Keep the acceptance criteria** — you need them numbered for section 6.
- Auth failure → say the Atlassian connector needs authorising in an interactive session, and
  stop. Ticket not found → report the exact error and ask for the correct key.
- **Never invent ticket content.**

## 2. Find the implementation (the part people skip)

Do these in parallel — they are independent and each one alone will mislead you.

**a. Grep the ticket ID in the source.** Many teams stamp it into doc comments
(`/** Scenario Detail (SS-783) — … */`). One grep can hand you the entire file set:

```
grep -rn "SS-783" client/src server/src --include=*.ts --include=*.tsx
```

If that comes back empty, fall back to grepping the feature's nouns from the ticket title.

**b. Check what is uncommitted.** Fresh ticket work is very often staged or unstaged, not
committed — `git log` alone will show you nothing:

```
git status --short          # staged (M/A), unstaged, and ?? untracked files
git diff --cached --stat    # what the staged work touches
git log --oneline -15
```

**Read the working tree, classify with git.** Every file you open — `cat`, Read, grep — is the
version **on disk**, which already contains committed, staged and unstaged edits merged together.
That is always the code you explain. Never trace from `git show`, a diff hunk, or a commit: a diff
shows what changed, not how the thing works, and reading only the staged version misses edits made
after staging. Git answers one question only — *how settled is this?* — which drives the status
column and section 6:

| Status | Meaning | How to treat it |
| ------ | ------- | --------------- |
| (clean) | committed | built |
| `M ` `A ` | staged | built |
| ` M` `MM` `AM` | edited after staging, or never staged | disk is newer than the index — disk wins |
| `??` | untracked | newest and least finished — flag as *in progress* |

Left column is the index, right column is the working tree. Untracked files are real work; say so
in section 6 rather than presenting them as shipped.

**If `git status` is clean and the grep found nothing**, the work is probably on another branch.
Check `git branch -a` and `git log --all --oneline --grep=<ID>` before concluding the ticket is
unimplemented — and if it lives on a branch you are not on, say which branch rather than tracing a
version the user isn't looking at.

**c. Learn the layout before assuming it.** Read the project's CLAUDE.md / AGENTS.md if present
and glance at the top-level folders. Never assume a stack or a folder convention.

> **Files can change under you mid-trace.** Another session may be actively writing this feature.
> If the harness reports a file changed on disk, take the new version as current, and if it is
> visibly mid-edit (a call with no matching import, a half-wired endpoint) note it as
> *in progress* in section 6 — never as broken, and never revert it.

**If the ticket has no implementation at all**, stop and say exactly that in one line, plus where
the work *would* go based on the sibling features you found. Don't manufacture a flow.

## 3. Trace it, layer by layer

Walk one direction and open **every** file on the path. Start at whichever end the ticket lives:
a screen → start at the click; an API/job/migration → start at the route or entry point.

A typical full-stack path — adapt the layer names to the actual stack, don't force these:

| Hop | What to establish | Where to look |
| --- | ----------------- | ------------- |
| Entry point | What the user clicks, and the URL it builds | the list/table/button that links here |
| Route | Which path maps to which page/handler | router config + route constants |
| Access check | Any permission gate **before** the fetch | privilege/guard hook in the page |
| Data hook | Cache key, when it's enabled, refetch behaviour | the query/state hook |
| API client | The exact method + path + params sent | the typed API function |
| Server route | The handler, its guards, its decorators | controller / route file |
| Business logic | Validation, orchestration, what runs in parallel | service |
| Data access | The real queries and joins | repository / DAO / ORM layer |
| Tables | Column names, joins, indexes, constraints | schema / migration files |

At each hop, capture **the specific thing**, not the layer's job description: the actual cache
key, the actual guard, the actual param names.

Four things are worth hunting for deliberately, because they're what a reader can't infer:

- **The isolation boundary.** Which predicate makes it impossible to read another tenant's,
  user's or parent record's data — and what happens when it fails (404 vs 403, and why).
- **Deliberate ordering.** Route declaration order, parallel vs sequential fetches, sort tiebreaks.
  If a comment explains it, that explanation is the most valuable line in your output.
- **The source-of-truth choice.** When two columns/tables could answer the same question, say
  which one the code reads and why (e.g. rolled-up per-row detail rather than a cached summary).
- **Whether anything writes the table at all.** Grep for the insert. A read path over a table with
  no writer means the screen renders its empty state in every environment — a fact that saves the
  reader an afternoon.

## 4. Write the output — this exact shape

````
# <ID> · <Title>

> **In one line:** <what this feature does, one plain sentence>

## 1. What the ticket is

<2–4 sentences. What screen/endpoint, who uses it, what it does and does not do.>

## 2. The flow, step by step

### Step 1 — <what happens, in the user's terms>
<The real file, the real symbol, the real value. A short snippet only when the exact
code is the point.>

### Step 2 — <…>
<…continue through every hop; 6–10 steps is typical>

## 3. Which tables the data comes from

<One line naming the database/scoping model, when there is one.>

| Table | What it gives this screen |
| ----- | ------------------------- |
| `table_name` | <the columns it contributes, and the join type if it's joined> |

<Below the table: any rule a reader could not guess — which column is the source of truth
and why, how values roll up, which join is the isolation boundary.>

## 4. API endpoints

| Method & path | Purpose | Status |
| ------------- | ------- | ------ |
| `GET /api/v1/…` | <what it returns> | ✅ working / 🔄 landing / ⬜ not built |

## 5. Input / output example

### Input
<the real request: method, path, headers that matter>

### Output
<real JSON, every field name copied from the DTO/type — never invented>

### What that renders
<a small ASCII sketch of the screen, when it's a UI ticket>

### Error cases
| Situation | Result |
| --------- | ------ |

## 6. Where it stands

**Built and working:** AC <list the numbers>.

**Still open:**

| AC | Item | Note |
| -- | ---- | ---- |
| 5 | <name> | <what exists, what's missing> |
````

Adapt the section set to the ticket — a pure-backend ticket has no "What that renders", a
UI-only ticket may have no tables section. Never keep an empty section, and never add sections
that weren't asked for.

## 5. Section 6 is mandatory — and it is the honest part

Always end with the AC status, even when everything is done ("**All 12 ACs implemented.**" plus
anything you noticed). Go through the ticket's acceptance criteria **one by one** against the code
you read, and mark what is genuinely there.

Count these as open, because they are:

- A button that renders but is `disabled`, or an action wired to a stub.
- A service method with no route wired to it, or a route whose imports don't resolve yet.
- Untracked (`??`) files — real work, not yet finished.
- **Missing tests**, when the project's rules require coverage. Check for the spec/test file
  rather than assuming it exists.
- Missing audit logging, permission gates, or validation the project's rules demand.

Never mark an AC done because the code "looks close". If you didn't see it work in the code, it
is open.

## Formatting rules — this is read in chat, make it scan

- **The "In one line" quote is mandatory.** The reader gets the answer without scrolling.
- Real values, field names, routes and codes go in `backticks`. File paths are always clickable
  markdown links relative to the workspace root (`[file.ts:42](path/to/file.ts#L42)`) — never bare
  text paths.
- **Tables for facts, prose for reasoning.** Don't squeeze a "why" into a table cell.
- Snippets only where the exact code is the point — 1–6 lines. This is a walkthrough, not a paste
  of the file.
- Plain words for the flow itself ("the page asks the server for…"), technical precision for the
  names ("`prediction_run_node_metric`"). A reader who doesn't know the codebase should follow the
  steps; a reader who does should be able to open every file you name.
- Multiple tickets → full format for each, separated by `---`.

## Guardrails

- **Explanation only.** Never edit, create or stage a file. Never propose an implementation plan
  or write the missing code — section 6 names the gaps and stops there.
- **Chat only.** Never write the walkthrough to a markdown file, however long it runs.
- **Never fabricate.** No invented file paths, column names, endpoints, JSON fields or snippets.
  Every field in the example response must come from a DTO/type/schema you actually opened. If
  you can't find something, say so in that spot.
- **Don't launch subagents or workflows** unless the user asks for one.
- No rules-applied table, no checklists, no effort estimates — nothing is being changed.
