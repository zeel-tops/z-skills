# 🛠️ z-skills

A personal set of **Claude Code skills** for the everyday parts of shipping code —
reviewing a change, resolving a merge, writing a commit or PR, and understanding a
ticket before touching it.

> 🔒 **House rule:** none of these skills ever commits, pushes, or creates a branch.
> They inspect, explain, and hand you text. **You own every git action.**

---

## 📋 The skills at a glance

| Skill | What it's for | Invoke | Touches files? |
| ----- | ------------- | ------ | -------------- |
| 🔍 **z-code-review** | Review a change across 5 axes before it merges | `/z-code-review` + auto | ❌ Read-only |
| 🔀 **z-fix-merge-conflicts** | Resolve a merge/rebase without losing either side | `/z-fix-merge-conflicts` + auto | ✏️ Edits conflicts |
| 🗃️ **z-check-drizzle-migration** | Catch silently-skipped drizzle migrations | `/z-check-drizzle-migration` + auto | ❌ Read-only |
| 📝 **z-pr-description** | Rich PR description with a Mermaid flow diagram | `/z-pr-description` + auto | 📄 Writes `PR_DESCRIPTION.md` |
| ✅ **z-precommit** | Clean the staged diff + write the commit message | `/z-precommit` | ✏️ Cleanup pass |
| 🧩 **z-simplify-ticket** | Explain a Jira ticket in plain English | `/z-simplify-ticket SS-562` | ❌ Read-only |
| 🧭 **z-explain-flow** | Trace a ticket's code path end to end | `/z-explain-flow SS-783` | ❌ Read-only |

*"+ auto" = Claude may also reach for it on its own when the situation matches.
The rest are slash-command only.*

---

## 🔍 z-code-review

Reviews a diff, branch, or PR across **correctness, readability, architecture,
security, and performance** — then ranks findings by leverage, so the structural
problem never sits buried under ten nits.

Resolves its own target (dirty tree → uncommitted work, clean tree → branch vs base,
or an explicit PR), labels every finding `🔴 Critical / Required / Consider / Nit`, and
reports without fixing until you say so.

📎 Criteria live in [`rubric.md`](z-code-review/rubric.md), loaded only during a review.

## 🔀 z-fix-merge-conflicts

**A conflict is two working features arriving at the same lines** — so the default is
*keep both*, never "pick a side to clear the markers."

Knows that rebase **swaps** which side is yours, sweeps for the file that broke but
never conflicted (the renamed symbol another branch still calls), and leaves genuinely
ambiguous conflicts untouched with markers intact so nothing half-merged gets committed.

📎 Backed by [`analyze-conflicts.py`](z-fix-merge-conflicts/analyze-conflicts.py) — shows
what *each side changed* versus their shared starting point.

## 🗃️ z-check-drizzle-migration

Drizzle **silently skips** any migration timestamped earlier than one already applied —
no error, no warning, just missing tables later. This is the read-only health check that
catches it after a merge or rebase.

Also flags journal conflicts, duplicate `idx`, orphaned `.sql` files, and snapshot
`prevId` forks.

📎 Backed by [`check-drizzle-migrations.py`](z-check-drizzle-migration/check-drizzle-migrations.py)
— exit codes: `0` clean · `1` warnings · `2` errors.

## 📝 z-pr-description

Writes a **full PR description to a file** — summary, Jira links, a Mermaid sequence
diagram with a numbered walkthrough, grouped changes, and a "try it out locally"
runbook with the real install/migrate/run commands.

Asks rather than invents when it can't find the ticket link or the route to open.

## ✅ z-precommit

The everyday pre-commit pass: tidies what's about to be committed (dead code, bloated
comments), writes a **Conventional Commits** message, and warns before you commit
straight to `main`.

🛡️ Refuses to edit any file with **both staged and unstaged changes** — re-staging it
would sweep your deliberately-unstaged work into the commit.

💡 `/z-precommit PR` gives a quick PR description instead.

## 🧩 z-simplify-ticket

Turns a Jira ticket into **plain English a non-developer can follow**: what it's about,
a `Before → After` walkthrough, and which files it lives in.

Reads the **comments**, not just the description — the real requirement is usually three
comments down.

## 🧭 z-explain-flow

The deep companion to the one above. Traces how the feature **actually works right
now**: click → route → endpoint → service → query → tables, with the real API endpoints,
a real request/response example, and an honest list of what's still open.

Every claim comes from a file it actually opened. 🚫 No invented paths or fields.

---

## 📦 Install

Symlink each skill into your Claude skills directory:

```bash
mkdir -p ~/.claude/skills

for s in z-*/; do
  name="${s%/}"
  rm -rf ~/.claude/skills/"$name"          # replace any existing copy
  ln -s "$PWD/$name" ~/.claude/skills/"$name"
done
```

> 💡 **Symlink rather than copy** — otherwise edits here never reach the version Claude
> actually runs, and the two quietly drift apart.
>
> ⚠️ The `rm -rf` replaces whatever is already installed. If you've ever edited a skill
> directly inside `~/.claude/skills/`, back it up first — that copy is about to go.

Then invoke any of them by name: `/z-code-review`, `/z-precommit`, and so on.
