---
name: z-code-review
description: >-
  Use when the user runs /z-code-review, or asks to review code, a diff, a PR/MR,
  or a branch before merging — whether the code was written by Claude, another
  agent, or a human. Also use after completing a feature implementation, after a
  bug fix (review the fix and its regression test), when refactoring existing
  code, or when the user asks to assess code quality, readability, architecture,
  security, or performance before a change enters the main branch.
---

# z-code-review

Review a change across five axes — correctness, readability, architecture, security,
performance — and hand back findings the author can act on, ordered by what actually
matters.

**The approval standard:** approve when the change definitely improves overall code
health, even if it isn't perfect. Perfect code doesn't exist. Don't block a change
because it isn't how you would have written it.

**Review-only.** Inspect, report, stop. Never stage, commit, push, or fix as part of
the review — offer to apply fixes afterwards and let the user say yes.

> Reviewing a large branch or a GitHub PR with inline comments? The built-in
> `/code-review` handles target resolution, effort levels, and posting comments to the
> PR. Use this skill for a structured review returned in chat.

## Step 0 — Resolve what you're reviewing

Never improvise scope. Work out the target first, state it, then gather the diff.

| User said | Target |
| --------- | ------ |
| nothing, and the tree is dirty | uncommitted work (staged + unstaged) |
| nothing, and the tree is clean | this branch vs its base |
| a branch name | that branch vs its base |
| a PR/MR number or URL | that PR's changes |
| a path | changes under that path only |

```bash
git status --short                                        # dirty or clean?
git rev-parse --abbrev-ref HEAD                           # current branch
git symbolic-ref --quiet --short refs/remotes/origin/HEAD # e.g. origin/main
```

For uncommitted work: `git diff` and `git diff --cached`.

For a branch, once you know the base:

```bash
git log origin/<base>..HEAD --oneline      # commits under review
git diff origin/<base>...HEAD --stat       # size and shape
git diff origin/<base>...HEAD              # the actual change
```

- **Prefer `origin/<base>` over a local base ref** — a stale local ref overstates the
  diff with already-merged work. If only a local ref exists, use it and say so.
- If `origin/HEAD` isn't set, fall back to whichever of `main`, `master`, `develop`
  exists.
- **If the current branch is the base branch and the tree is clean, stop** — there is
  nothing to review. Say so.
- For a PR/MR: GitHub → `gh pr diff <number>`; GitLab → the GitLab MCP
  `get_merge_request_changes` / `get_merge_request_details`.

**Size ceiling.** Past roughly 1,500 changed lines, don't pull the whole diff blind.
Read `--stat` first, review the files carrying the real logic in full, skim the rest —
and **name the files you skimmed** in the output. A review that silently skipped half
the change is worse than one that admits its scope.

## Step 1 — Understand the intent

Before judging the code, establish what it is trying to do: the task or spec it
implements, the behaviour that should change, and the constraints it is working under.
Read the PR description, the commit messages, and any linked ticket. **A review that
doesn't know the intent can only check style.**

If you genuinely cannot tell what the change is for, ask — don't review it against a
purpose you invented.

## Step 2 — Review the tests first

Tests reveal intent and coverage faster than the implementation does:

- Do tests exist for this change?
- Do they test behaviour, or implementation details?
- Are edge cases covered — null, empty, boundary, error paths?
- Would they actually catch a regression, or do they pass no matter what?
- Bug fix? There must be a test that fails without the fix.

## Step 3 — Review the implementation

Walk the change with the five axes in mind. **Read `rubric.md` (next to this file) for
the full criteria** — correctness, readability, architecture, security, performance,
plus structural remedies, change sizing, and dependency discipline.

Two rules that decide whether the review is worth reading:

- **Propose the move, not just the problem.** "This is complex" leaves the author
  guessing. Name the restructuring — collapse the branches, extract the helper, make
  the type boundary explicit.
- **Judge the resulting structure, not the diff size.** A small diff can bolt a branch
  onto an unrelated flow or push a file past a healthy size. Both are design smells,
  not nits.

## Step 4 — Rank and label every finding

Order by leverage: correctness and security first, then structural problems and missed
simplifications, then everything else. **If you have one structural problem and ten
nits, the structural problem *is* the review.** A few high-conviction findings beat a
long list.

| Label | Meaning | Author action |
| ----- | ------- | ------------- |
| 🔴 **Critical** | Blocks merge | Security hole, data loss, broken functionality |
| **Required** | Must fix before merge | Correctness, structure, missing test |
| **Consider** | Worth weighing, not required | Suggestion with a real trade-off |
| **Nit** | Optional | Style, naming, formatting — author may ignore |
| **FYI** | Informational | No action; context for later |

Every finding needs a file and line, and a concrete fix. Unlabelled feedback makes
authors treat optional suggestions as mandatory.

## Step 5 — Check the verification story

- What tests were run, and did they pass? Run them yourself if cheap and safe.
- Does the build pass?
- Was it verified manually — screenshots for UI, before/after for performance?
- Never claim a check passed without having run it. Report real output.

## Output format

Print in chat. Drop any section that doesn't apply — no empty headings.

````markdown
## Review: <what you reviewed>

**Scope:** <N commits, M files, +X/−Y> vs `origin/<base>` <— note if you skimmed anything>
**Verdict:** ✅ Approve · ⚠️ Approve with follow-ups · 🔴 Request changes

### Findings

**🔴 Critical — <one-line title>**
[file.ts:42](path/to/file.ts#L42)
<What's wrong, why it matters in concrete terms, and the fix.>

**Required — <title>**
[file.ts:88](path/to/file.ts#L88)
<…>

**Nit — <title>**
[file.ts:12](path/to/file.ts#L12) — <one line>

### What's solid
<1–3 specific things done well. Not flattery — real observations.>

### Verification
- Tests: <what ran, what happened>
- Build: <result, or "not run">
````

File paths are clickable markdown links relative to the workspace root, never bare text.

## Honesty rules

- **Don't rubber-stamp.** "LGTM" with no evidence of review helps nobody.
- **Don't soften real issues.** "Might be a minor concern" about a bug that will hit
  production is dishonest.
- **Quantify.** "This N+1 adds ~50ms per row" beats "this could be slow."
- **Push back on bad approaches.** Sycophancy is a review failure mode. Say it directly
  and propose the alternative.
- **Accept override gracefully.** If the author has full context and disagrees, defer.
  Comment on the code, never the person.
- **Give AI-written code more scrutiny, not less.** It is confident and plausible when
  wrong.

## Guardrails

- **Never fix during review.** Report first. Offer: "Want me to apply these?" and wait.
- **Never delete code you found unused** — list it and ask. See dead-code hygiene in
  `rubric.md`.
- **Never claim a test or build passed** without the command output to back it.
- **No commits, no pushes, no branch changes.** The review is output only.

## Before you send — self-check

- The scope line names the real base and admits anything skimmed.
- Every finding has a file, a line, a label, and a concrete fix.
- Findings are ordered by leverage — nothing important sits below a nit.
- Every claim about tests or builds traces to output you actually saw.
- The verdict matches the findings (no 🔴 Critical sitting under ✅ Approve).
