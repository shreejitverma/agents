#!/usr/bin/env python3
"""post_edit: Claude Code PostToolUse lint feedback for the file just written.

Registered in claude/settings.json as PostToolUse on Write|Edit|MultiEdit.

After an edit it runs the formatter and linter the file's own project already
configures, and only those, so a repo without a config gets no opinion:

    *.py, *.pyi   ruff check and ruff format --check, when a ruff.toml,
                  .ruff.toml, or pyproject.toml with a [tool.ruff] table sits
                  between the file and its repository root
    C and C++     clang-format --dry-run, when a .clang-format or _clang-format
                  sits between the file and its repository root

Findings go to stderr with exit code 2, which Claude Code shows to the model
after the tool has already run, so it fixes them in the same turn instead of
discovering them at the no-mistakes gate. A clean file prints nothing.

This is feedback, not a gate: a missing tool, a timeout, an unreadable payload,
and every internal error exit 0, so a hook problem never blocks work. The
gate stays no-mistakes and CI.

The idea is adapted from ECC's post-edit quality hooks
(https://github.com/affaan-m/ecc, MIT License, Copyright (c) 2026 Affaan
Mustafa), rewritten for ruff and clang-format.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

TIMEOUT_SECONDS = 8  # per tool run; settings.json gives the hook 20 in total
MAX_LINES = 30  # lines of findings shown per file, so a broken file cannot flood the context

PYTHON_SUFFIXES = {".py", ".pyi"}
CPP_SUFFIXES = {".c", ".h", ".cc", ".cpp", ".cxx", ".c++", ".hh", ".hpp", ".hxx", ".ipp", ".tpp", ".inl"}
RUFF_CONFIGS = ("ruff.toml", ".ruff.toml")
CLANG_FORMAT_CONFIGS = (".clang-format", "_clang-format")


def find_config(start: Path, names: tuple[str, ...], pyproject: bool = False) -> Path | None:
    """Nearest directory from start upward holding one of names, bounded by the repository root."""
    for d in (start, *start.parents):
        if any((d / n).is_file() for n in names):
            return d
        if pyproject and _pyproject_configures_ruff(d / "pyproject.toml"):
            return d
        if (d / ".git").exists():
            return None
    return None


def _pyproject_configures_ruff(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return any(line.strip().startswith("[tool.ruff") for line in text.splitlines())


def run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str] | None:
    """Run a tool; None when it is missing or does not finish in time."""
    if shutil.which(argv[0]) is None:
        return None
    try:
        return subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT_SECONDS, stdin=subprocess.DEVNULL
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _clip(text: str) -> str:
    lines = [line for line in text.strip().splitlines() if line.strip()]
    if len(lines) > MAX_LINES:
        lines = [*lines[:MAX_LINES], f"... {len(lines) - MAX_LINES} more lines"]
    return "\n".join(lines)


def check_python(path: Path) -> list[str]:
    root = find_config(path.parent, RUFF_CONFIGS, pyproject=True)
    if root is None:
        return []
    findings = []
    # --force-exclude makes ruff honour the project's exclude list even for a
    # file named explicitly on the command line.
    lint = run(
        ["ruff", "check", "--quiet", "--no-fix", "--force-exclude", "--output-format", "concise", str(path)], root
    )
    if lint is not None and lint.returncode == 1:
        findings.append(f"ruff check found problems:\n{_clip(lint.stdout)}")
    fmt = run(["ruff", "format", "--check", "--quiet", "--force-exclude", str(path)], root)
    if fmt is not None and fmt.returncode == 1:
        findings.append(f"ruff format would reformat this file; run: ruff format {path}")
    return findings


def check_cpp(path: Path) -> list[str]:
    root = find_config(path.parent, CLANG_FORMAT_CONFIGS)
    if root is None:
        return []
    fmt = run(["clang-format", "--dry-run", "--Werror", "--style=file", str(path)], root)
    if fmt is None:
        return []
    # Each violation is three lines of source excerpt, and the fix is one
    # command either way, so report the count rather than the excerpts. Any
    # other failure, such as an unreadable .clang-format, is not a finding.
    places = fmt.stderr.count("[-Wclang-format-violations]")
    if places == 0:
        return []
    plural = "s" if places != 1 else ""
    return [f"clang-format would reformat this file in {places} place{plural}; run: clang-format -i {path}"]


def feedback(payload: Mapping[str, object], env: Mapping[str, str]) -> str:
    """Return the findings text for Claude (empty when there is nothing to say)."""
    if env.get("CLAUDE_POST_EDIT_DISABLE") == "1":
        return ""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    raw = tool_input.get("file_path")
    if not isinstance(raw, str) or not raw:
        return ""
    path = Path(raw)
    if not path.is_absolute():
        cwd = payload.get("cwd")
        path = Path(cwd if isinstance(cwd, str) else os.getcwd()) / path
    if not path.is_file():
        return ""
    suffix = path.suffix.lower()
    if suffix in PYTHON_SUFFIXES:
        findings = check_python(path)
    elif suffix in CPP_SUFFIXES:
        findings = check_cpp(path)
    else:
        return ""
    if not findings:
        return ""
    body = "\n\n".join(findings)
    return f"post-edit check for {path} (the project's own config; fix before moving on):\n{body}"


def main() -> int:
    try:
        stdin = sys.stdin.read()
        payload = json.loads(stdin) if stdin.strip() else {}
        text = feedback(payload if isinstance(payload, dict) else {}, os.environ)
    except Exception as exc:  # fail open: feedback must never block work
        print(f"post_edit: internal error, skipping: {exc!r}", file=sys.stderr)
        return 0
    if not text:
        return 0
    print(text, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
