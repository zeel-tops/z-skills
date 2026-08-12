#!/usr/bin/env python3
"""Drizzle migration health checker (stdlib only).

Discovers every drizzle migrations folder (any directory containing
meta/_journal.json), then reports, per folder:

  ERRORS (break migrate or generate)
    - merge conflict markers in the journal, snapshots, or .sql files
    - unparseable journal / snapshot JSON
    - journal entries whose .sql or meta snapshot file is missing
    - snapshot prevId collisions (two snapshots claiming the same parent
      -> `drizzle-kit generate/check` refuses to run)
    - SKIP RISK: journal `when` timestamps not strictly increasing in entry
      order. drizzle's migrator applies entries in journal order but skips
      any entry whose `when` <= the last-applied migration's created_at, so
      an out-of-order entry is silently skipped on already-migrated DBs.
    - migrations present on the base branch but missing here (lost history)

  WARNINGS (suspicious, usually from hand-edited journals)
    - duplicate idx / duplicate when values
    - orphan .sql or snapshot files not referenced by the journal
    - snapshot chain not linear (prevId != previous entry's id)
    - SKIP RISK vs base branch / merge counterpart: migrations new on this
      branch that sort BEFORE migrations the other side already applied

Usage:
  python3 check-drizzle-migrations.py [--base <ref>] [--repo <path>]

Exit codes: 0 = clean, 1 = warnings only, 2 = errors.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

CONFLICT_MARKERS = ("<<<<<<<", "=======", ">>>>>>>")
PRUNE_DIRS = {"node_modules", ".git", "dist", "build", "coverage", ".next"}


def run_git(repo: str, *args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", repo, *args],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.infos: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def info(self, msg: str) -> None:
        self.infos.append(msg)


def find_migration_folders(repo: str) -> list[str]:
    folders = []
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in PRUNE_DIRS]
        if os.path.basename(root) == "meta" and "_journal.json" in files:
            folders.append(os.path.dirname(root))
    return sorted(folders)


def has_conflict_markers(path: str) -> bool:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return False
    return any(f"\n{m}" in text or text.startswith(m) for m in CONFLICT_MARKERS)


def load_journal(path: str, rep: Report) -> dict | None:
    if has_conflict_markers(path):
        rep.error(f"UNRESOLVED MERGE CONFLICT markers in {path}")
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        rep.error(f"journal unreadable/unparseable: {path}: {exc}")
        return None


def check_folder(folder: str, repo: str, base_ref: str | None, rep: Report) -> None:
    rel = os.path.relpath(folder, repo)
    journal_path = os.path.join(folder, "meta", "_journal.json")
    journal = load_journal(journal_path, rep)
    if journal is None:
        return
    entries = journal.get("entries", [])
    rep.info(f"[{rel}] {len(entries)} journal entries")

    # -- conflict markers in sql / snapshots ------------------------------
    for name in sorted(os.listdir(folder)):
        if name.endswith(".sql") and has_conflict_markers(os.path.join(folder, name)):
            rep.error(f"[{rel}] conflict markers in {name}")
    meta_dir = os.path.join(folder, "meta")
    for name in sorted(os.listdir(meta_dir)):
        if name.endswith(".json") and name != "_journal.json":
            if has_conflict_markers(os.path.join(meta_dir, name)):
                rep.error(f"[{rel}] conflict markers in meta/{name}")

    # -- journal internal consistency -------------------------------------
    tags = [e.get("tag") for e in entries]
    if len(tags) != len(set(tags)):
        dupes = sorted({t for t in tags if tags.count(t) > 1})
        rep.error(f"[{rel}] duplicate journal tags: {dupes}")
    idxs = [e.get("idx") for e in entries]
    dup_idx = sorted({i for i in idxs if idxs.count(i) > 1})
    if dup_idx:
        rep.warn(f"[{rel}] duplicate journal idx values: {dup_idx}")
    whens = [e.get("when") for e in entries]
    dup_when = sorted({w for w in whens if whens.count(w) > 1})
    if dup_when:
        rep.warn(f"[{rel}] duplicate `when` timestamps: {dup_when}")
    for prev, cur in zip(entries, entries[1:]):
        if (cur.get("when") or 0) <= (prev.get("when") or 0):
            rep.error(
                f"[{rel}] SKIP RISK: '{cur.get('tag')}' (when={cur.get('when')}) is "
                f"ordered after '{prev.get('tag')}' (when={prev.get('when')}) but has a "
                f"smaller/equal timestamp — drizzle will SKIP it on any database already "
                f"migrated past '{prev.get('tag')}'. Reorder journal entries by `when`, "
                f"or re-stamp the newer migration with a later timestamp."
            )

    # -- files present for every entry, no orphans -------------------------
    # Snapshots are named after the tag's numeric/timestamp prefix only:
    # tag `0004_glorious_snowbird` -> meta/0004_snapshot.json. A missing .sql
    # crashes the migrator (ERROR); a missing snapshot is tolerated by drizzle
    # (common for hand-authored data migrations) but degrades generate diffs.
    snap_by_prefix: dict[str, dict] = {}
    prefixes: list[str] = []
    for e in entries:
        tag = e.get("tag") or ""
        prefix = tag.split("_", 1)[0]
        prefixes.append(prefix)
        if not os.path.exists(os.path.join(folder, f"{tag}.sql")):
            rep.error(f"[{rel}] journal entry '{tag}' has no {tag}.sql file")
        if prefix in snap_by_prefix:
            continue
        snap_path = os.path.join(meta_dir, f"{prefix}_snapshot.json")
        if not os.path.exists(snap_path):
            rep.warn(
                f"[{rel}] journal entry '{tag}' has no meta/{prefix}_snapshot.json "
                f"(fine for hand-authored data migrations; schema migrations need one)"
            )
            continue
        try:
            with open(snap_path, encoding="utf-8") as fh:
                snap_by_prefix[prefix] = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            rep.error(f"[{rel}] snapshot meta/{prefix}_snapshot.json unparseable: {exc}")
    dup_prefixes = sorted({p for p in prefixes if prefixes.count(p) > 1})
    if dup_prefixes:
        rep.warn(
            f"[{rel}] multiple journal entries share a snapshot prefix: {dup_prefixes} "
            f"— their snapshots overwrite each other; consider re-stamping one."
        )
    tag_set = set(tags)
    prefix_set = set(prefixes)
    for name in sorted(os.listdir(folder)):
        if name.endswith(".sql") and name[:-4] not in tag_set:
            rep.warn(f"[{rel}] orphan migration file not in journal: {name}")
    for name in sorted(os.listdir(meta_dir)):
        if name.endswith("_snapshot.json") and name[: -len("_snapshot.json")] not in prefix_set:
            rep.warn(f"[{rel}] orphan snapshot not in journal: meta/{name}")

    # -- snapshot parent chain (over unique snapshot FILES) ------------------
    parent_of: dict[str, list[str]] = {}
    for prefix, snap in snap_by_prefix.items():
        prev_id = snap.get("prevId")
        if prev_id:
            parent_of.setdefault(prev_id, []).append(prefix)
    for prev_id, children in sorted(parent_of.items()):
        if len(children) > 1:
            rep.error(
                f"[{rel}] snapshot prevId COLLISION: {sorted(children)} all claim parent "
                f"{prev_id[:8]}… — `drizzle-kit generate/check` will refuse to run. "
                f"Relink prevId so the chain is linear in journal order."
            )
    ordered_prefixes: list[str] = []
    for p in prefixes:
        if p in snap_by_prefix and (not ordered_prefixes or ordered_prefixes[-1] != p):
            ordered_prefixes.append(p)
    for prev_p, cur_p in zip(ordered_prefixes, ordered_prefixes[1:]):
        prev_id = snap_by_prefix[cur_p].get("prevId")
        expect = snap_by_prefix[prev_p].get("id")
        if prev_id and expect and prev_id != expect:
            rep.warn(
                f"[{rel}] snapshot chain not linear: '{cur_p}'.prevId != "
                f"'{prev_p}'.id (often benign after reconciliation migrations, "
                f"but verify with `drizzle-kit check`)"
            )

    # -- cross-branch skip risk --------------------------------------------
    journal_rel = os.path.relpath(journal_path, repo)
    for label, ref in (("base", base_ref), ("merge counterpart", merge_head_ref(repo))):
        if not ref:
            continue
        other = read_journal_at(repo, ref, journal_rel)
        if other is None:
            continue
        compare_journals(rel, label, ref, entries, other.get("entries", []), rep)


def merge_head_ref(repo: str) -> str | None:
    git_dir = run_git(repo, "rev-parse", "--git-dir")
    if git_dir and os.path.exists(os.path.join(repo, git_dir.strip(), "MERGE_HEAD")):
        return "MERGE_HEAD"
    return None


def read_journal_at(repo: str, ref: str, journal_rel: str) -> dict | None:
    raw = run_git(repo, "show", f"{ref}:{journal_rel}")
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def compare_journals(
    rel: str,
    label: str,
    ref: str,
    ours: list[dict],
    theirs: list[dict],
    rep: Report,
) -> None:
    our_tags = {e.get("tag"): e for e in ours}
    their_tags = {e.get("tag"): e for e in theirs}
    lost = [t for t in their_tags if t not in our_tags]
    if lost and label == "base":
        rep.error(
            f"[{rel}] migrations on {ref} are MISSING from this branch's journal: "
            f"{lost} — a DB migrated on {ref} has rows this journal doesn't know."
        )
    new_here = [e for t, e in our_tags.items() if t not in their_tags]
    if not new_here:
        return
    applied_whens = [e.get("when") or 0 for t, e in their_tags.items() if t in our_tags]
    max_applied = max(applied_whens, default=0)
    at_risk = [e for e in new_here if (e.get("when") or 0) <= max_applied]
    if at_risk:
        names = [e.get("tag") for e in at_risk]
        rep.warn(
            f"[{rel}] SKIP RISK vs {label} ({ref}): new migrations {names} have "
            f"timestamps older than migrations already on {ref} — any database "
            f"already migrated there will silently skip them. Re-stamp them with a "
            f"fresh timestamp (regenerate) if that ref's DBs matter."
        )


def detect_base_ref(repo: str, explicit: str | None) -> str | None:
    if explicit:
        return explicit
    for ref in ("origin/main", "origin/master", "main", "master"):
        if run_git(repo, "rev-parse", "--verify", "--quiet", ref) is not None:
            head = run_git(repo, "rev-parse", "HEAD")
            tip = run_git(repo, "rev-parse", ref)
            if head and tip and head.strip() == tip.strip():
                return None  # on the base branch itself; nothing to compare
            return ref
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="base ref to compare against (default: origin/main|master)")
    parser.add_argument("--repo", default=".", help="repository root (default: cwd)")
    args = parser.parse_args()

    repo = os.path.abspath(args.repo)
    top = run_git(repo, "rev-parse", "--show-toplevel")
    if top:
        repo = top.strip()
    folders = find_migration_folders(repo)
    if not folders:
        print("No drizzle migration folders (meta/_journal.json) found.")
        return 0

    base_ref = detect_base_ref(repo, args.base)
    rep = Report()
    for folder in folders:
        check_folder(folder, repo, base_ref, rep)

    for line in rep.infos:
        print(f"  i  {line}")
    for line in rep.warnings:
        print(f"  ⚠  WARN  {line}")
    for line in rep.errors:
        print(f"  ✗  ERROR {line}")
    print()
    if rep.errors:
        print(f"RESULT: {len(rep.errors)} error(s), {len(rep.warnings)} warning(s) — migrations are NOT safe to run.")
        return 2
    if rep.warnings:
        print(f"RESULT: no errors, {len(rep.warnings)} warning(s) — review before migrating.")
        return 1
    print("RESULT: all checks passed — journal order, files, and snapshot chain look healthy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
