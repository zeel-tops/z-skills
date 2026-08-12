---
name: z-simplify-ticket
description: Explain a Jira ticket in plain English — type, a before → after walkthrough, and where it lives in the code. Explanation only; never changes code or writes files.
argument-hint: "<ticket-id or jira-url> [more…]"
disable-model-invocation: true
---

# Simplify a Jira ticket

**What you produce:** a plain-English explanation of one ticket, grounded in the real code,
printed **in chat only** — never written to a file. Exactly the sections in the template below.
Nothing else — no task plan, no implementation, no acceptance-criteria mapping, no checklist,
no rules-applied table.

## 0. Read the argument

- A bare ID (`SS-562`, `proj-123`, case-insensitive) → uppercase it and use it.
- A full Jira URL (`https://…/browse/SS-562`) → extract the key from the URL.
- Extra words around it (`explain SS-562 again please`) → use every token that looks like a
  ticket key or Jira URL and ignore the rest.
- A number with no project prefix (`562`) → ask which project it belongs to. Don't guess the
  prefix from branch names or earlier tickets.
- Several IDs → explain each one in turn, in the order given, same format, separated by a `---`
  rule.
- No argument → ask for the ticket ID and stop. Don't guess one from branch names or
  recent conversation.

## 1. Fetch the ticket

Load the Atlassian tools first — they are deferred:
`ToolSearch` → `select:mcp__atlassian__getJiraIssue,mcp__atlassian__getAccessibleAtlassianResources`
(the second supplies the cloud ID the first needs). If those exact names don't exist, ToolSearch
for `jira` and use the closest get-issue tool.

- Read the **summary, issue type, status, description, acceptance criteria, comments, and linked
  issues.**
- **Comments usually carry the real requirement** — a ticket's description is often stale and the
  actual ask is three comments down. Never stop at the description. If the issue response contains
  no comments, fetch them explicitly (a separate call, an expand parameter, or ToolSearch for a
  comments tool) — don't conclude there are none.
- When comments contradict each other or the description: the **latest comment from the ticket's
  reporter wins; if the reporter never commented, the latest comment wins.** Either way, name the
  conflict on the `> ⚠️ Unclear:` line.
- Linked issues: use the keys and summaries already in the response — don't fetch each linked
  ticket. Fetch one (at most one) only if this ticket is meaningless without it.
- If the fetch fails on auth, say the Atlassian connector needs authorising in an interactive
  session and stop. If the ticket isn't found (wrong key, no permission), report the exact error
  and ask for the correct key. Any other fetch error → report it verbatim and stop. **Never guess
  or invent ticket content.**
- If the ticket references screenshots or attachments you can't view, say they exist — don't
  describe images you haven't seen.
- If the ticket's status is already Done/Closed/Resolved, say so in the "In one line" quote —
  Before is then "what used to happen", not "today".

## 2. Decide the type

Trust Jira's issue-type field first, mapped to one of three:

| Jira type                                            | Use            |
| ---------------------------------------------------- | -------------- |
| Bug, Defect                                          | 🐞 Bug         |
| Story, Task, Sub-task, New Feature, Epic             | 🧩 Task        |
| Improvement, Suggestion, Enhancement, Change Request | 💡 Suggestion  |
| Anything else (Spike, Incident, custom types)        | infer — below  |

If the field is missing, too generic, or not in the table, read the description instead:
something behaving wrong → Bug; new behaviour being asked for → Task; "we should…" / "it would be
better if…" / "consider…" → Suggestion.

For an **Epic**, keep 🧩 Task, but "What this is about" should briefly list its child tickets —
keys and one-line summaries from the epic's own links, without fetching every child — and
Before → After describes the end state of the whole epic.

## 3. Ground it in the real code (do this before writing anything)

This step is what makes the output worth reading — without it you are just paraphrasing Jira.

- Discover the repo layout first: read the project's CLAUDE.md if there is one and glance at the
  top-level folders, then grep for the feature or module the ticket names. Don't assume a layout.
- **Read the files that matter.** Don't list paths from a grep hit you never opened. Reading
  3–8 files is usually enough — this is an explanation, not an audit. With several tickets,
  stay at the low end of that budget for each.
- For UI tickets, check whether the project documents shared/common components (CLAUDE.md or a
  rules/docs folder) — the component the ticket needs often already exists, and that changes how
  you explain the work.
- If the ticket's feature doesn't exist in this workspace at all (it may belong to another repo or
  service), say so up front and let "Where in the code" be that one honest line.
- **Never invent a file path, prop name, column or snippet** — if you genuinely cannot find the
  code, the honest one-liner above is the answer.

## 4. Write the output — this exact shape

The `#` heading starts with the type emoji, so the kind is visible at a glance. Lines marked
"only" are dropped when they don't apply; everything else always appears.

````
# <type emoji> <ID> · <the ticket's summary>

> **In one line:** <the entire ticket in one plain sentence>

**Type:** <🐞 Bug | 🧩 Task | 💡 Suggestion> · **Area:** <Frontend | Backend | Both | other — name it> · `<module or feature>`

### What this is about

<Paragraph, bullets, or both — whichever explains it fastest. See the guide below.>

### Before → After

**Before — today**
1. <who meets this and where — a real page or entry point, real values>
2. <what happens next>
3. <the current (wrong or missing) result>

**After — once this is done**
1. <the same steps, mirrored>
2. <…>
3. <the new result instead>

**Why:** <🐞 Bug only — the root cause in everyday words>

**Worth it?** <💡 Suggestion only — one line on cost and whether it looks worth doing>

### Where in the code

| File | Today |
| ---- | ----- |
| [Name.tsx](path/to/Name.tsx) | <what it does right now> |

> ⚠️ **Unclear:** <only when genuinely ambiguous — one line naming what is unclear>
````

If no related code was found, replace the table with one honest line — *"No related code found in
this workspace; this likely lives in \<other repo/service\>."*

### Formatting rules — this is read in chat, make it scan

- **The "In one line" quote is mandatory.** A reader should get the ticket without scrolling;
  everything below it is elaboration.
- Spend the space on **Before → After** — it is the heart of the output and should be detailed.
  Keep every other section tight (short paragraphs, 2–4 sentences) so the whole thing still scans.
- **Tables: two columns, short cells.** Explanations live in prose, not squeezed into cells.
- Real values, names, routes and codes go in `backticks`; file paths are always clickable
  markdown links relative to the workspace root — never bare text paths.
- Multiple tickets → full format for each, separated by `---`.

### "What this is about" — pick the shape that reads clearest

| Ticket shape                                | Use                             |
| ------------------------------------------- | ------------------------------- |
| One idea that needs context or a "why"      | A paragraph, 2–4 sentences      |
| Several separate facts, conditions or rules | Bullets                         |
| A story that then splits into cases         | A paragraph, then a few bullets |

Never force bullets onto something that is one continuous thought, and never bury five separate
conditions inside one paragraph.

### "Before → After" — one section, adapted per type

Always include it. Make it a **detailed walkthrough, not a one-liner**: a numbered story of who
meets this change, where, what they do, and what they see at each step — 3–6 steps per side, with
real names, pages and values taken from the code you just read, not made up. Before and After must
mirror each other step for step, so the difference jumps out on its own.

The "user" is whoever actually meets the change. For a ticket with no screen — an API, a nightly
job, a migration — walk through the system instead: what calls what, with what values, and what
comes back. **Never invent a UI journey for a ticket that has no UI.**

- **🐞 Bug** — Before is what the user sees now (wrong), After is what they should see. Close with
  one short **Why** line naming the root cause in everyday words. Explain the cause; do **not**
  write the fix code.
- **🧩 Task** — Before is how it works today, After is how it works once the ticket is done. When
  the feature is brand new, "doesn't exist today" is a perfectly good Before — still show it.
- **💡 Suggestion** — Before is the current situation, After is what it would look like if we
  accept. Close with the one-line **Worth it?** verdict — cost, and whether it looks worth doing.

Stacked, numbered **Before** / **After** walkthroughs are the default. Switch to a two-column
table only when the comparison is genuinely row-by-row (e.g. field mappings); add a short fenced
block when exact values matter (a code, a date, an error message).

### "Where in the code"

One to four rows — as many files as genuinely matter, no padding and no more than four. Real
paths only, as markdown links relative to the workspace root, and only files you actually opened.
The "Today" column says what the file does **now**, not what it will do after the change.

## Writing rules

- Write for someone who has seen neither the ticket nor the code. A non-developer should be able
  to follow "What this is about" and "Before → After"; only "Where in the code" may be technical.
- Plain words over technical ones — "the page shows" not "the component renders", "saved" not
  "persisted". When a technical term is unavoidable, explain it in everyday words the first time
  it appears (a tenant, a scope, an internal product name).
- Output in simple English even when the ticket is written in jargon, shorthand, or another
  language.
- Keep all the sections even when the ticket is trivial — just make them shorter.
- If the ticket is genuinely ambiguous, use the `> ⚠️ Unclear:` line at the end — one line, not an
  open-questions section.

## Guardrails

- **Explanation only.** Never edit, create or stage a file, and never propose implementation steps
  — that's a job for an implementation skill or a normal dev request.
- **Chat only.** Never write the explanation to a markdown file, even if it is long.
- **Never fabricate.** No invented ticket text, file paths, column names or snippets.
- No add/change/remove breakdowns, no checklists, no AC tables, no effort estimates — those were
  deliberately cut from this format.

## Before you send — a 20-second self-check

- The `> **In one line:**` quote is present and is actually one sentence.
- Before and After mirror each other step for step, 3–6 steps per side.
- The type-specific closer is there (**Why** for a bug, **Worth it?** for a suggestion) — and
  absent for every other type.
- Every file path is a clickable link to a file you opened in this session.
- Every value, path and name traces back to the ticket or the code — nothing imagined.
