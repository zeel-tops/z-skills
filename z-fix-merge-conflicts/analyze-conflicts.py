#!/usr/bin/env python3
"""Analyse an in-progress merge / rebase / cherry-pick conflict.

Read-only with one exception: it writes the three git stages of each conflicted
file into `<git-dir>/z-conflict-analysis/` so they can be read directly. That
directory lives inside `.git`, so it is never committed and never shows up in
`git status`.

Prints, per conflicted file:
  * the conflict kind (both modified / both added / deleted by one side)
  * what YOUR side changed relative to the common starting point
  * what the INCOMING side changed relative to the common starting point
  * flags for files that need special handling (lock files, migrations, i18n,
    generated files, binaries)

Usage:
    python3 analyze-conflicts.py [--json] [--file <path>] [--max-diff-lines N]
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ANALYSIS_DIRNAME = 'z-conflict-analysis'
DEFAULT_MAX_DIFF_LINES = 400

# Files that must never be hand-merged hunk by hunk.
SPECIAL_FILE_RULES: list[tuple[str, str, str]] = [
    (
        r'(^|/)(pnpm-lock\.yaml|package-lock\.json|yarn\.lock|bun\.lockb)$',
        'lock-file',
        'Never hand-merge. Take one side, then regenerate by re-running the '
        'install from the repo root.',
    ),
    (
        r'(^|/)meta/_journal\.json$',
        'drizzle-journal',
        'Keep BOTH migrations. Renumber idx and bump the later `when` so both '
        'still run in order. Then run the drizzle migration check.',
    ),
    (
        r'(^|/)meta/\d+_snapshot\.json$',
        'drizzle-snapshot',
        'Snapshot chain (prevId) forks on merge. Do not hand-merge — resolve '
        'the journal first, then verify with the drizzle migration check.',
    ),
    (
        r'(^|/)drizzle/.*\.sql$',
        'migration-sql',
        'Never drop a migration to clear the conflict. Both sides shipped real '
        'schema changes; both must survive.',
    ),
    (
        r'(^|/)locales/[^/]+/[^/]+\.json$',
        'i18n',
        'Keep BOTH sets of keys. Then check the mirror locale file has the '
        'matching pair for every key kept.',
    ),
    (
        r'\.(generated|gen)\.(ts|tsx|js|json)$|(^|/)(dist|build|coverage)/',
        'generated',
        'Do not hand-merge generated output. Resolve the source, then '
        'regenerate.',
    ),
    (
        r'(^|/)(CHANGELOG\.md)$',
        'changelog',
        'Almost always additive — keep both sets of entries, newest first.',
    ),
]

STAGE_LABELS = {1: 'base', 2: 'ours', 3: 'theirs'}


def run_git(args: list[str], *, binary: bool = False, check: bool = True):
    """Run a git command and return stdout (str, or bytes when binary)."""
    result = subprocess.run(
        ['git', *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        message = result.stderr.decode('utf-8', 'replace').strip()
        raise RuntimeError(f'git {" ".join(args)} failed: {message}')
    if binary:
        return result.stdout
    return result.stdout.decode('utf-8', 'replace')


def git_dir() -> Path:
    return Path(run_git(['rev-parse', '--absolute-git-dir']).strip())


def repo_root() -> Path:
    return Path(run_git(['rev-parse', '--show-toplevel']).strip())


def name_of_commit(rev: str) -> str:
    """Best-effort human name for a commit-ish."""
    for args in (
        ['name-rev', '--name-only', '--exclude=tags/*', rev],
        ['describe', '--all', '--exact-match', rev],
    ):
        out = run_git(args, check=False).strip()
        if out and out != 'undefined':
            return re.sub(r'^(remotes/|heads/|refs/heads/|refs/remotes/)', '', out)
    return run_git(['rev-parse', '--short', rev], check=False).strip() or rev


def read_first_line(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8', errors='replace').splitlines()[0].strip()
    except (OSError, IndexError):
        return ''


def detect_operation(gd: Path) -> dict:
    """Work out which operation is mid-flight and what each side really is.

    The side mapping is the whole point of this function. During a MERGE,
    stage 2 ("ours") is your branch. During a REBASE it is the opposite way
    round: stage 2 is the upstream you are replaying onto, and stage 3
    ("theirs") is your own work. Mislabelling this is the single most common
    way a conflict gets resolved backwards.
    """
    current = run_git(['rev-parse', '--abbrev-ref', 'HEAD'], check=False).strip()

    if (gd / 'MERGE_HEAD').exists():
        incoming = name_of_commit(read_first_line(gd / 'MERGE_HEAD'))
        return {
            'operation': 'merge',
            'your_side': current,
            'your_stage': 2,
            'incoming_side': incoming,
            'incoming_stage': 3,
            'continue_command': 'git merge --continue',
            'abort_command': 'git merge --abort',
            'note': 'Standard mapping: stage 2 (ours) is your branch, '
                    'stage 3 (theirs) is what you pulled in.',
        }

    for rebase_dir in ('rebase-merge', 'rebase-apply'):
        rd = gd / rebase_dir
        if not rd.exists():
            continue
        head_name = read_first_line(rd / 'head-name')
        your_branch = re.sub(r'^refs/heads/', '', head_name) or current
        onto_rev = read_first_line(rd / 'onto')
        onto = name_of_commit(onto_rev) if onto_rev else 'the upstream branch'
        return {
            'operation': 'rebase',
            # SIDES ARE SWAPPED during a rebase — see docstring.
            'your_side': your_branch,
            'your_stage': 3,
            'incoming_side': onto,
            'incoming_stage': 2,
            'continue_command': 'git rebase --continue',
            'abort_command': 'git rebase --abort',
            'note': 'REBASE — sides are swapped. Stage 3 (theirs) is YOUR '
                    'commit being replayed; stage 2 (ours) is the upstream '
                    'branch you are rebasing onto.',
        }

    for marker, op, cont, abort in (
        ('CHERRY_PICK_HEAD', 'cherry-pick', 'git cherry-pick --continue', 'git cherry-pick --abort'),
        ('REVERT_HEAD', 'revert', 'git revert --continue', 'git revert --abort'),
    ):
        if (gd / marker).exists():
            incoming = name_of_commit(read_first_line(gd / marker))
            return {
                'operation': op,
                'your_side': current,
                'your_stage': 2,
                'incoming_side': incoming,
                'incoming_stage': 3,
                'continue_command': cont,
                'abort_command': abort,
                'note': f'{op}: stage 2 (ours) is your branch, stage 3 '
                        f'(theirs) is the commit being applied.',
            }

    return {'operation': 'none', 'your_side': current}


def list_conflicts() -> dict[str, set[int]]:
    """Map each unmerged path to the set of stages git has for it."""
    stages: dict[str, set[int]] = {}
    for line in run_git(['ls-files', '-u', '-z']).split('\0'):
        if not line.strip():
            continue
        meta, _, path = line.partition('\t')
        parts = meta.split()
        if len(parts) < 3 or not path:
            continue
        stages.setdefault(path, set()).add(int(parts[2]))
    return stages


def classify_kind(present: set[int], op: dict) -> tuple[str, str]:
    """Turn the set of available stages into a plain-English conflict kind."""
    your_stage = op.get('your_stage', 2)
    incoming_stage = op.get('incoming_stage', 3)
    has_your = your_stage in present
    has_incoming = incoming_stage in present

    if 1 not in present:
        return (
            'both-added',
            'Both sides created this file independently — there is no shared '
            'starting point to compare against.',
        )
    if has_your and not has_incoming:
        return (
            'deleted-by-incoming',
            'The incoming side DELETED this file while your side changed it. '
            'Decide deliberately: was it deleted on purpose, or does your '
            'change need to move somewhere else?',
        )
    if has_incoming and not has_your:
        return (
            'deleted-by-you',
            'Your side DELETED this file while the incoming side changed it. '
            'Confirm the incoming change is not lost by the deletion.',
        )
    return ('both-modified', 'Both sides edited this file.')


def special_flags(path: str) -> list[dict]:
    return [
        {'flag': flag, 'guidance': guidance}
        for pattern, flag, guidance in SPECIAL_FILE_RULES
        if re.search(pattern, path)
    ]


def stage_bytes(path: str, stage: int) -> bytes | None:
    result = subprocess.run(
        ['git', 'show', f':{stage}:{path}'],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def is_binary(blob: bytes | None) -> bool:
    return blob is not None and b'\0' in blob[:8000]


def write_stage_files(out_dir: Path, path: str, blobs: dict[int, bytes | None]) -> dict[str, str]:
    target = out_dir / path
    target.parent.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    suffix = Path(path).suffix
    for stage, blob in blobs.items():
        if blob is None:
            continue
        dest = target.with_name(f'{target.name}.{STAGE_LABELS[stage]}{suffix}')
        dest.write_bytes(blob)
        written[STAGE_LABELS[stage]] = str(dest)
    return written


def make_diff(before: bytes | None, after: bytes | None, label: str, max_lines: int) -> list[str]:
    if before is None or after is None:
        return []
    before_lines = before.decode('utf-8', 'replace').splitlines(keepends=True)
    after_lines = after.decode('utf-8', 'replace').splitlines(keepends=True)
    diff = list(
        difflib.unified_diff(
            before_lines, after_lines,
            fromfile=f'{label} (common starting point)',
            tofile=label,
            n=3,
        )
    )
    if len(diff) > max_lines:
        diff = diff[:max_lines] + [
            f'\n... diff truncated at {max_lines} lines — read the stage files '
            f'listed above for the full picture.\n'
        ]
    return diff


def count_conflict_hunks(work_tree_path: Path) -> int:
    try:
        text = work_tree_path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return 0
    return len(re.findall(r'^<{7}', text, flags=re.MULTILINE))


def analyse_file(path: str, present: set[int], op: dict, out_dir: Path,
                 root: Path, max_lines: int) -> dict:
    kind, kind_note = classify_kind(present, op)
    your_stage = op.get('your_stage', 2)
    incoming_stage = op.get('incoming_stage', 3)

    blobs = {stage: stage_bytes(path, stage) for stage in sorted(present)}
    binary = any(is_binary(blob) for blob in blobs.values())

    entry: dict = {
        'path': path,
        'kind': kind,
        'kind_note': kind_note,
        'is_binary': binary,
        'special': special_flags(path),
        'conflict_hunks': count_conflict_hunks(root / path),
        'stage_files': {} if binary else write_stage_files(out_dir, path, blobs),
        'your_changes': [],
        'incoming_changes': [],
    }

    if binary:
        entry['kind_note'] += (
            ' This is a BINARY file — never hand-merge it. Pick one side '
            'deliberately, or regenerate it from source.'
        )
        return entry

    base = blobs.get(1)
    entry['your_changes'] = make_diff(
        base, blobs.get(your_stage), f'YOUR side ({op.get("your_side", "?")})', max_lines
    )
    entry['incoming_changes'] = make_diff(
        base, blobs.get(incoming_stage), f'INCOMING side ({op.get("incoming_side", "?")})', max_lines
    )
    return entry


def print_report(op: dict, entries: list[dict], out_dir: Path) -> None:
    print('=' * 78)
    print(f'OPERATION IN PROGRESS: {op["operation"].upper()}')
    print('=' * 78)
    print(f'  Your work           : {op.get("your_side")}   (git stage {op.get("your_stage")})')
    print(f'  Coming in           : {op.get("incoming_side")}   (git stage {op.get("incoming_stage")})')
    print(f'  {op.get("note", "")}')
    print(f'\n  Stage files written to: {out_dir}')
    print(f'  Conflicted files: {len(entries)}\n')

    for index, entry in enumerate(entries, start=1):
        print('-' * 78)
        print(f'[{index}] {entry["path"]}')
        print('-' * 78)
        print(f'  Kind          : {entry["kind"]} — {entry["kind_note"]}')
        print(f'  Conflict hunks: {entry["conflict_hunks"]}')
        for special in entry['special']:
            print(f'  ** SPECIAL ({special["flag"]}): {special["guidance"]}')
        if entry['stage_files']:
            print('  Stage files   :')
            for name, file_path in entry['stage_files'].items():
                print(f'      {name:<7}: {file_path}')

        if entry['is_binary']:
            print()
            continue

        print('\n  === What YOUR side changed (vs the common starting point) ===')
        print(''.join(entry['your_changes']) or '      (no change on this side)\n')
        print('  === What the INCOMING side changed (vs the common starting point) ===')
        print(''.join(entry['incoming_changes']) or '      (no change on this side)\n')

    print('=' * 78)
    print('Nothing has been modified in the working tree. Resolve deliberately.')
    print('=' * 78)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='emit machine-readable JSON')
    parser.add_argument('--file', action='append', dest='files',
                        help='limit analysis to this path (repeatable)')
    parser.add_argument('--max-diff-lines', type=int, default=DEFAULT_MAX_DIFF_LINES,
                        help=f'truncate each diff (default {DEFAULT_MAX_DIFF_LINES})')
    args = parser.parse_args()

    try:
        gd = git_dir()
        root = repo_root()
    except RuntimeError as error:
        print(f'Not a git repository: {error}', file=sys.stderr)
        return 2

    op = detect_operation(gd)
    conflicts = list_conflicts()

    if op['operation'] == 'none' and not conflicts:
        payload = {
            'operation': 'none',
            'message': 'No merge, rebase or cherry-pick is in progress and '
                       'there are no unmerged files. Nothing to resolve.',
        }
        print(json.dumps(payload, indent=2) if args.json else payload['message'])
        return 1

    if args.files:
        wanted = set(args.files)
        conflicts = {path: stages for path, stages in conflicts.items() if path in wanted}

    out_dir = gd / ANALYSIS_DIRNAME
    out_dir.mkdir(parents=True, exist_ok=True)

    entries = [
        analyse_file(path, stages, op, out_dir, root, args.max_diff_lines)
        for path, stages in sorted(conflicts.items())
    ]

    if args.json:
        print(json.dumps({'operation': op, 'analysis_dir': str(out_dir),
                          'files': entries}, indent=2))
    else:
        print_report(op, entries, out_dir)
    return 0


if __name__ == '__main__':
    sys.exit(main())
