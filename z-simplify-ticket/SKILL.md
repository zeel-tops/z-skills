---
name: z-simplify-ticket
description: Use when the user runs /z-simplify-ticket, or asks what a Jira ticket means — "explain SS-562", "what do we have to do in SS-562", "simplify this ticket", "summarise this ticket in simple language". Fetches the ticket, works out whether it is a bug, task or suggestion, grounds it in the current codebase, and explains it in plain English with a concrete before → after example. Explanation only — it never writes or changes code.
---

# Simplify a Jira ticket

Takes one argument: a ticket ID (`SS-562`, case-insensitive). Optional flag: `--file`.

**What you produce:** a plain-English explanation of one ticket, grounded in the real code, in
exactly three sections. Nothing else — no task plan, no implementation, no acceptance-criteria
mapping, no checklist, and **no rules-applied table** (this is a prose answer with zero file
changes, which the Storm Predict response-checklist rule explicitly exempts).

## 1. Fetch the ticket

Load the Atlassian tools first — they are deferred:
`ToolSearch` → `select:mcp__atlassian__getJiraIssue,mcp__atlassian__getAccessibleAtlassianResources`

- Uppercase the ID (`ss-562` → `SS-562`).
- Read the **summary, issue type, description, acceptance criteria, comments, and linked issues.**
- **Comments usually carry the real requirement** — a ticket's description is often stale and the
  actual ask is three comments down. Never stop at the description.
- If the fetch fails on auth, say the Atlassian connector needs authorising in an interactive
  session and stop. **Never guess or invent ticket content.**

## 2. Decide the type

Trust Jira's issue-type field first, mapped to one of three:

| Jira type                                            | Use           |
| ---------------------------------------------------- | ------------- |
| Bug, Defect                                          | 🐞 Bug        |
| Story, Task, Sub-task, New Feature, Epic             | 🧩 Task       |
| Improvement, Suggestion, Enhancement, Change Request | 💡 Suggestion |

If the field is missing or too generic, read the description instead: something behaving wrong →
Bug; new behaviour being asked for → Task; "we should…" / "it would be better if…" / "consider…" →
Suggestion.

## 3. Ground it in the real code (do this before writing anything)

This step is what makes the output worth reading — without it you are just paraphrasing Jira.

- Grep for the feature or module the ticket names, using the current repo's own layout. In Storm
  Predict that is `client/src/features/<feature>/` and `server/src/<module>/`; in another repo,
  find the equivalent before assuming.
- **Read the files that matter.** Don't list paths from a grep hit you never opened.
- For UI tickets in Storm Predict, check `.claude/rules/common-components.md` — the shared
  component the ticket needs often already exists, and that changes how you explain the work.
- **Never invent a file path, prop name, column or snippet.** If you genuinely cannot find the
  code, say so in that section rather than filling it with plausible guesses.

## 4. Write the output

````
# <ID> · <Title>

**Type:** 🐞 Bug / 🧩 Task / 💡 Suggestion · **Area:** Frontend / Backend / Both · `<module>`

### What this is about

<Paragraph, bullets, or both — whichever explains it fastest. See the guide below.>

### Before → After

<A concrete example with real values, then a two-column comparison. See the per-type guide.>

### Where in the code

| File | Today |
| ---- | ----- |
| [Name.tsx](client/src/…/Name.tsx) | <what it does right now> |
````

### "What this is about" — pick the shape that reads clearest

| Ticket shape                                | Use                             |
| ------------------------------------------- | ------------------------------- |
| One idea that needs context or a "why"      | A paragraph, 2–4 sentences      |
| Several separate facts, conditions or rules | Bullets                         |
| A story that then splits into cases         | A paragraph, then a few bullets |

Never force bullets onto something that is one continuous thought, and never bury five separate
conditions inside one paragraph.

### "Before → After" — one section, adapted per type

Always include it. Always anchor it with **a concrete example using real values** — a real tenant,
a real page, a real code, a real user — taken from the code you just read, not made up.

- **🐞 Bug** — Before is what the user sees now (wrong), After is what they should see. Close with
  one short **Why** line naming the root cause in everyday words. Explain the cause; do **not**
  write the fix code.
- **🧩 Task** — Before is how it works today, After is how it works once the ticket is done. When
  the feature is brand new, "doesn't exist today" is a perfectly good Before — still show it.
- **💡 Suggestion** — Before is the current situation, After is what it would look like if we
  accept. Close with one line on cost and whether it looks worth doing.

A short fenced block is often clearer than a table for the example; use whichever fits, and use
both when the example needs a walkthrough and the comparison needs columns.

### "Where in the code"

Two to four rows, no more. Real paths only, as markdown links relative to the workspace root. The
"Today" column says what the file does **now**, not what it will do after the change.

## Writing rules

- Write for someone who has seen neither the ticket nor the code.
- Short sentences, everyday words. Explain each domain term the first time it appears — Event
  Commander, scope, tenant, OP Center — instead of assuming it.
- Output in simple English even when the ticket is written in jargon, shorthand, or another
  language.
- Keep the three sections even when the ticket is trivial — just make them shorter.
- If the ticket is genuinely ambiguous, add one short line at the end naming what is unclear.
  One line, not an open-questions section.

## Guardrails

- **Explanation only.** Never edit, create or stage a file, and never propose implementation steps
  — a build skill such as `/dev-task` does that.
- **Never fabricate.** No invented ticket text, file paths, column names or snippets.
- No add/change/remove breakdowns, no checklists, no AC tables, no effort estimates — those were
  deliberately cut from this format.

## `--file`

With `--file`, also write the same output to `<ID>-simplified.md` at the repo root. Without it,
print to chat only.
