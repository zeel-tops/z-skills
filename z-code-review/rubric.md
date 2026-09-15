# Review rubric

Reference for `z-code-review`. Read this during Step 3, when a review is actually
underway.

## 1. Correctness

Does the code do what it claims to do?

- Does it match the spec or task requirements?
- Are edge cases handled — null, empty, boundary values?
- Are error paths handled, not just the happy path?
- Does it pass the tests, and are the tests testing the right things?
- Off-by-one errors, race conditions, state inconsistencies?

## 2. Readability & simplicity

Can another engineer understand this without the author explaining it?

- Are names descriptive and consistent with project conventions? (No `temp`, `data`,
  `result` without context.)
- Is the control flow straightforward — no nested ternaries, no deep callbacks?
- Is related code grouped, with clear module boundaries?
- Any "clever" tricks that should be simplified?
- **Could this be done in fewer lines?** 1000 lines where 100 suffice is a failure.
- **Are abstractions earning their complexity?** Don't generalise until the third case.
- Do comments clarify non-obvious intent — without restating obvious code?
- Dead-code artifacts: no-op variables, backwards-compat shims, `// removed` comments?
- **Is a new conditional bolted onto an unrelated flow?** That's a design smell, not a
  nit — push the logic into its own helper, state, or policy instead of tangling an
  existing path.
- **Do repeated conditionals on the same shape appear?** They signal a missing model or
  dispatcher. A "temporary" branch is usually permanent debt.

## 3. Architecture

Does the change fit the system's design?

- Does it follow existing patterns, or introduce a new one? If new, is it justified?
- Does it maintain clean module boundaries?
- Is there duplication that should be shared?
- Do dependencies flow in the right direction — no cycles?
- Is the abstraction level appropriate: not over-engineered, not over-coupled?
- **Does this refactor reduce complexity or just relocate it?** Count the concepts a
  reader must hold to follow the change. If a "cleaner" version leaves that count
  unchanged, it isn't cleaner. Prefer the restructuring that makes whole branches,
  modes, or layers disappear over one that re-centralises the same logic. Prefer
  deleting an abstraction to polishing it.
- **Is feature-specific logic leaking into a shared module?** Keep logic in its owning
  layer, reuse the canonical helper instead of a near-duplicate, and don't normalise
  architectural drift.
- **Are type boundaries explicit?** Question gratuitous `any`/`unknown`/optional/casts
  and silent fallbacks that paper over an unclear invariant — making the boundary
  explicit often makes the surrounding control flow simpler.

## 4. Security

- Is user input validated and sanitised?
- Are secrets kept out of code, logs, and version control?
- Is authentication/authorisation checked where needed?
- Are SQL queries parameterised — no string concatenation?
- Are outputs encoded against XSS?
- Are dependencies trusted, maintained, and free of known vulnerabilities?
- Is data from external sources (APIs, logs, user content, config) treated as untrusted
  and validated at the boundary before use in logic or rendering?

## 5. Performance

- N+1 query patterns?
- Unbounded loops or unconstrained fetching?
- Synchronous operations that should be async?
- Unnecessary re-renders in UI components?
- Missing pagination on list endpoints?
- Large objects created in hot paths?

---

## Structural remedies

When you flag a structural problem, propose the move. Reach for a named restructuring:

- **Replace a chain of conditionals** with a typed model or explicit dispatcher.
- **Collapse duplicate branches** into a single clearer flow.
- **Separate orchestration from business logic** so each reads on its own.
- **Move feature-specific logic** out of a shared module into the package that owns it.
- **Reuse the canonical helper** instead of a bespoke near-duplicate.
- **Make a type boundary explicit** so downstream branching disappears.
- **Delete a pass-through wrapper** that adds indirection without clarifying the API.
- **Extract a helper, or split a large file** into focused modules.

Prefer the remedy that removes moving pieces over one that spreads the same complexity
around.

## Change sizing

```
~100 lines changed   → Good. Reviewable in one sitting.
~300 lines changed   → Acceptable if it's a single logical change.
~1000 lines changed  → Too large. Split it.
```

**Watch file size, not just diff size.** A small diff can still push a file past a
healthy boundary — around 1000 *total* lines in one file (distinct from the ~1000
*changed*-lines threshold) is an inspection signal, not a hard cap. When a change
materially grows an already-large file, ask whether to extract helpers or modules
*first*. Decompose, then add.

**What counts as one change:** a single self-contained modification addressing one
thing, including its tests, leaving the system functional. One part of a feature — not
the whole feature.

| Splitting strategy | How | When |
| ------------------ | --- | ---- |
| **Stack** | Submit a small change, start the next on top of it | Sequential dependencies |
| **By file group** | Separate changes for groups needing different reviewers | Cross-cutting concerns |
| **Horizontal** | Shared code/stubs first, then consumers | Layered architecture |
| **Vertical** | Smaller full-stack slices of the feature | Feature work |

**Acceptable large changes:** whole-file deletions and automated refactors, where the
reviewer verifies intent rather than every line.

**Separate refactoring from feature work.** A change that refactors *and* adds behaviour
is two changes. Small cleanups (a rename) can ride along at reviewer discretion.

## Change descriptions

The first line must be short, imperative, and standalone — "Delete the FizzBuzz RPC",
not "Deleting the FizzBuzz RPC" — informative enough that someone searching history
understands it without the diff. The body covers what is changing and why: context,
decisions, reasoning not visible in the code, links to tickets or benchmarks, and honest
acknowledgement of shortcomings.

Anti-patterns: "Fix bug", "Fix build", "Add patch", "Moving code from A to B", "Phase 1".

(For drafting commit messages rather than reviewing them, use `z-precommit`.)

## Dependency discipline

Before any new dependency:

1. Does the existing stack already solve this? (Often it does.)
2. How large is it? Check bundle impact.
3. Is it actively maintained? Check last commit and open issues.
4. Known vulnerabilities? (`npm audit`)
5. What's the licence, and is it compatible?

**Rule:** prefer the standard library and existing utilities. Every dependency is a
liability.

## Dead-code hygiene

After a refactor or a replacement, check for orphaned code: identify what is now
unreachable, list it explicitly, and **ask before deleting**.

```
DEAD CODE IDENTIFIED:
- formatLegacyDate() in src/utils/date.ts — replaced by formatDate()
- OldTaskCard in src/components/ — replaced by TaskCard
- LEGACY_API_URL in src/config.ts — no remaining references
→ Safe to remove these?
```

Don't leave dead code lying around; don't silently delete what you're unsure about.

---

## Common rationalisations

| Rationalisation | Reality |
| --------------- | ------- |
| "It works, that's good enough" | Working code that's unreadable, insecure, or architecturally wrong creates debt that compounds. |
| "I wrote it, so I know it's correct" | Authors are blind to their own assumptions. |
| "We'll clean it up later" | Later never comes. The review is the gate — require cleanup before merge. |
| "AI-generated code is probably fine" | AI code needs more scrutiny, not less. Confident and plausible even when wrong. |
| "The tests pass, so it's good" | Tests don't catch architecture problems, security holes, or unreadable code. |
| "The refactor makes it cleaner" | Relocating complexity isn't reducing it. If the reader holds the same number of concepts, nothing improved. |
| "It's only a small addition to this file" | Small diffs still push files past a healthy size and bolt branches onto unrelated flows. Judge the resulting structure. |

## Red flags in the change

- A refactor that moves code without reducing the concepts a reader must hold
- A change that grows an already-large file instead of decomposing it
- New conditionals scattered into unrelated code paths (a missing abstraction)
- A bespoke helper duplicating an existing canonical one
- Feature logic placed in a shared module
- A silent fallback hiding an unclear invariant
- A bug fix with no regression test
- Security-sensitive code with no security-focused scrutiny

**Presumptive blockers:** surface and propose the simpler design for each of the above.
Escalate to **Required** only when the change actively makes the structure worse.

## Red flags in your own review

- "LGTM" with no evidence you read the code
- Only checking whether tests pass
- Findings with no severity label
- A long list of nits with the real problem buried inside it
- Accepting "I'll fix it later"
