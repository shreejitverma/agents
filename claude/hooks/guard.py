#!/usr/bin/env python3
"""guard: Claude Code PreToolUse guard for destructive shell commands and check-config edits.

Registered in claude/settings.json:

    guard.py bash   PreToolUse on Bash
    guard.py edit   PreToolUse on Write|Edit|MultiEdit

Decisions, printed as PreToolUse JSON on stdout (exit 0 in every case):

    block  always deny: bypassing git hooks, force-pushing or deleting a shared
           branch, recursive force-removal of a critical path.
    ask    destructive but sometimes intended (reset --hard, clean -f, rm -rf of a
           non-artifact path, branch -D, DROP TABLE, ...). Asks when a human is at
           the keyboard; allowed silently in unattended runs so claude -p pipelines
           and firstmate crewmates never wedge on a prompt nobody will answer.
    config editing an existing lint/format/gate config. Asks when a human is
           present; denied when unattended, because weakening the check instead of
           fixing the code is exactly the unattended failure mode.

A human is present when CLAUDE_CODE_SESSION_ATTENDED=1 (claude -p sets 0) and
FM_TASK_ID is unset (firstmate exports it into every ship and scout pane).

This is a backstop against accidents, not a sandbox: a determined caller can
always reach the same effect some other way (a script file, python -c, ...).
Parse failures and internal errors fail open with a note on stderr, so a guard
bug never blocks work; the user can always run a refused command with the `!`
prefix, which bypasses tool hooks.

Adapted from ECC (https://github.com/affaan-m/ecc, MIT License, Copyright (c)
2026 Affaan Mustafa): scripts/hooks/block-no-verify.js, the destructive-command
classifier in scripts/hooks/gateguard-fact-force.js, and
scripts/hooks/config-protection.js.
"""

from __future__ import annotations

import json
import os
import posixpath
import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

BLOCK = "block"
ASK = "ask"
_SEVERITY = {ASK: 1, BLOCK: 2}

MAX_DEPTH = 6  # recursion bound for sh -c / eval / $(...) nesting

# --------------------------------------------------------------------------
# Presence
# --------------------------------------------------------------------------


def human_present(env: Mapping[str, str]) -> bool:
    if env.get("FM_TASK_ID"):
        return False
    attended = env.get("CLAUDE_CODE_SESSION_ATTENDED")
    if attended is None:  # older Claude Code: fall back to the entrypoint
        return env.get("CLAUDE_CODE_ENTRYPOINT") == "cli"
    return attended == "1"


# --------------------------------------------------------------------------
# Shell tokenizer
# --------------------------------------------------------------------------
#
# A deliberately small bash-subset lexer. It yields simple-command segments as
# lists of words, split on ; & && | || |& newlines and ( ) group boundaries, with
# quotes removed, redirections and their targets dropped, and comments skipped.
# Command substitution, backticks and process substitution bodies are returned
# separately so the caller scans them as command lines of their own. Heredoc
# bodies are returned with the segment that introduced them, because a body is
# data unless it feeds a shell or a SQL client.

_SEPARATOR_CHARS = ";&|\n()"


@dataclass
class Heredoc:
    delimiter: str
    strip_tabs: bool
    segment_index: int
    body: str = ""


@dataclass
class Lexed:
    segments: list[list[str]] = field(default_factory=list)
    substitutions: list[str] = field(default_factory=list)
    heredocs: list[Heredoc] = field(default_factory=list)


def _match_close(text: str, start: int, open_ch: str, close_ch: str) -> int:
    """Index of the close_ch matching an already-consumed open_ch, quote aware; -1 if none."""
    depth = 1
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "'":
            j = text.find("'", i + 1)
            if j == -1:
                return -1
            i = j + 1
            continue
        if c == '"':
            i = _skip_double_quoted(text, i + 1)
            if i == -1:
                return -1
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _skip_double_quoted(text: str, start: int) -> int:
    """Index just past the closing double quote of a string opened before start; -1 if unterminated."""
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == '"':
            return i + 1
        if c == "$" and i + 1 < n and text[i + 1] == "(":
            j = _match_close(text, i + 2, "(", ")")
            if j == -1:
                return -1
            i = j + 1
            continue
        if c == "`":
            j = _find_backtick(text, i + 1)
            if j == -1:
                return -1
            i = j + 1
            continue
        i += 1
    return -1


def _find_backtick(text: str, start: int) -> int:
    i = start
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == "`":
            return i
        i += 1
    return -1


def lex(text: str) -> Lexed:
    out = Lexed()
    segment: list[str] = []
    word: list[str] = []
    in_word = False
    skip_next_word = False  # the word after a redirection operator is its target
    pending_heredoc: Heredoc | None = None  # delimiter word expected next
    queued_heredocs: list[Heredoc] = []  # bodies start after the next newline
    i = 0
    n = len(text)

    def end_word() -> None:
        nonlocal word, in_word, skip_next_word, pending_heredoc
        if not in_word:
            return
        value = "".join(word)
        word = []
        in_word = False
        if pending_heredoc is not None:
            pending_heredoc.delimiter = value
            queued_heredocs.append(pending_heredoc)
            pending_heredoc = None
            return
        if skip_next_word:
            skip_next_word = False
            return
        segment.append(value)

    def end_segment() -> None:
        nonlocal segment
        end_word()
        if segment:
            out.segments.append(segment)
        segment = []

    def consume_heredoc_bodies(pos: int) -> int:
        """pos is just past a newline; read every queued body and return the new position."""
        while queued_heredocs:
            doc = queued_heredocs.pop(0)
            lines: list[str] = []
            while pos <= n:
                nl = text.find("\n", pos)
                line = text[pos:] if nl == -1 else text[pos:nl]
                pos = n + 1 if nl == -1 else nl + 1
                check = line.lstrip("\t") if doc.strip_tabs else line
                if check == doc.delimiter:
                    break
                lines.append(line)
            doc.body = "\n".join(lines)
            out.heredocs.append(doc)
        return min(pos, n)

    while i < n:
        c = text[i]

        if c == "\\":
            if i + 1 < n and text[i + 1] == "\n":  # line continuation
                i += 2
                continue
            if i + 1 < n:
                word.append(text[i + 1])
            in_word = True
            i += 2
            continue

        if c == "'":
            j = text.find("'", i + 1)
            if j == -1:
                raise ValueError("unterminated single quote")
            word.append(text[i + 1 : j])
            in_word = True
            i = j + 1
            continue

        if c == '"':
            i = _lex_double_quoted(text, i + 1, word, out)
            in_word = True
            continue

        if c == "$" and i + 1 < n and text[i + 1] == "(":
            if i + 2 < n and text[i + 2] == "(":  # arithmetic $(( ... ))
                j = _match_close(text, i + 3, "(", ")")
                if j == -1:
                    raise ValueError("unterminated arithmetic expansion")
                j = j + 1 if j + 1 < n and text[j + 1] == ")" else j
                word.append("0")
                in_word = True
                i = j + 1
                continue
            j = _match_close(text, i + 2, "(", ")")
            if j == -1:
                raise ValueError("unterminated command substitution")
            out.substitutions.append(text[i + 2 : j])
            word.append("$(...)")
            in_word = True
            i = j + 1
            continue

        if c == "$" and i + 1 < n and text[i + 1] == "{":
            j = _match_close(text, i + 2, "{", "}")
            if j == -1:
                raise ValueError("unterminated parameter expansion")
            word.append(text[i : j + 1])
            in_word = True
            i = j + 1
            continue

        if c == "`":
            j = _find_backtick(text, i + 1)
            if j == -1:
                raise ValueError("unterminated backtick")
            out.substitutions.append(text[i + 1 : j])
            word.append("$(...)")
            in_word = True
            i = j + 1
            continue

        if c in "<>":
            if i + 1 < n and text[i + 1] == "(":  # process substitution
                j = _match_close(text, i + 2, "(", ")")
                if j == -1:
                    raise ValueError("unterminated process substitution")
                out.substitutions.append(text[i + 2 : j])
                i = j + 1
                continue
            # A bare fd number glued to the operator (2>file) is not an argument.
            if in_word and word and "".join(word).isdigit():
                word = []
                in_word = False
            else:
                end_word()
            j = i
            while j < n and text[j] in "<>&|-":
                j += 1
            op = text[i:j]
            i = j
            if op.startswith("<<") and not op.startswith("<<<"):
                pending_heredoc = Heredoc("", op.startswith("<<-"), len(out.segments))
            elif op.endswith("&") and i < n and (text[i].isdigit() or text[i] == "-"):
                i += 1  # >&2, <&-: the fd is part of the operator
            else:
                skip_next_word = True
            continue

        if c == "&" and i + 1 < n and text[i + 1] == ">":  # &> and &>> redirect both streams
            end_word()
            i += 2
            if i < n and text[i] == ">":
                i += 1
            skip_next_word = True
            continue

        if c in _SEPARATOR_CHARS:
            end_segment()
            i += 1
            if c == "\n" and queued_heredocs:
                i = consume_heredoc_bodies(i)
            continue

        if c in " \t\r":
            end_word()
            i += 1
            continue

        if c == "#" and not in_word:
            nl = text.find("\n", i)
            i = n if nl == -1 else nl
            continue

        word.append(c)
        in_word = True
        i += 1

    end_segment()
    if queued_heredocs:  # heredoc at the very end with no newline yet
        consume_heredoc_bodies(n)
    return out


def _lex_double_quoted(text: str, start: int, word: list[str], out: Lexed) -> int:
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\" and i + 1 < n and text[i + 1] in '$`"\\\n':
            if text[i + 1] != "\n":
                word.append(text[i + 1])
            i += 2
            continue
        if c == '"':
            return i + 1
        if c == "$" and i + 1 < n and text[i + 1] == "(":
            j = _match_close(text, i + 2, "(", ")")
            if j == -1:
                raise ValueError("unterminated command substitution")
            out.substitutions.append(text[i + 2 : j])
            word.append("$(...)")
            i = j + 1
            continue
        if c == "`":
            j = _find_backtick(text, i + 1)
            if j == -1:
                raise ValueError("unterminated backtick")
            out.substitutions.append(text[i + 1 : j])
            word.append("$(...)")
            i = j + 1
            continue
        word.append(c)
        i += 1
    raise ValueError("unterminated double quote")


# --------------------------------------------------------------------------
# Command classification
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    level: str
    reason: str


def _base(token: str) -> str:
    return token.rsplit("/", 1)[-1].lower()


_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_SHELL_KEYWORDS = {
    "!",
    "{",
    "}",
    "if",
    "then",
    "else",
    "elif",
    "fi",
    "do",
    "done",
    "while",
    "until",
    "time",
    "case",
    "esac",
    "in",
}
_SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
_SQL_CLIENTS = {
    "psql",
    "mysql",
    "mariadb",
    "sqlite3",
    "duckdb",
    "clickhouse-client",
    "clickhouse",
    "sqlcmd",
    "cockroach",
}

# Wrapper -> option flags that consume a following value.
_WRAPPER_VALUE_FLAGS: dict[str, set[str]] = {
    "sudo": {"-u", "-g", "-h", "-p", "-C", "-D", "-r", "-t", "-U", "-T"},
    "doas": {"-u", "-C"},
    "env": {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"},
    "nice": {"-n", "--adjustment"},
    "ionice": {"-c", "-n", "-p"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"},
    "gtimeout": {"-s", "--signal", "-k", "--kill-after"},
    "stdbuf": {"-i", "-o", "-e"},
    "xargs": {
        "-I",
        "-i",
        "-n",
        "-P",
        "-L",
        "-l",
        "-d",
        "-E",
        "-s",
        "-a",
        "--delimiter",
        "--max-args",
        "--max-procs",
        "--arg-file",
        "--replace",
    },
    "command": set(),
    "builtin": set(),
    "exec": {"-a"},
    "nohup": set(),
    "caffeinate": {"-t", "-w"},
    "chronic": set(),
}
# Wrappers whose first positional argument is not the command (timeout DURATION cmd).
_WRAPPER_LEADING_POSITIONALS = {"timeout": 1, "gtimeout": 1}


def unwrap(words: list[str]) -> list[str]:
    """Strip keywords, VAR=value prefixes and wrapper commands; return the real command words."""
    i = 0
    for _ in range(16):
        while i < len(words) and (words[i] in _SHELL_KEYWORDS or _ASSIGNMENT.match(words[i])):
            i += 1
        if i >= len(words):
            return []
        base = _base(words[i])
        if base not in _WRAPPER_VALUE_FLAGS:
            return words[i:]
        value_flags = _WRAPPER_VALUE_FLAGS[base]
        i += 1
        while i < len(words):
            w = words[i]
            if w == "--":
                i += 1
                break
            if base == "env" and _ASSIGNMENT.match(w):
                i += 1
                continue
            if not w.startswith("-") or w == "-":
                break
            if w in value_flags:
                i += 2
                continue
            i += 1
        i += _WRAPPER_LEADING_POSITIONALS.get(base, 0)
    return words[i:]


def _shell_script_arg(words: list[str]) -> str | None:
    """For `bash [-opts] -c SCRIPT`, return SCRIPT."""
    for i, w in enumerate(words[1:], start=1):
        if w == "--":
            return None
        if w.startswith("-") and not w.startswith("--") and "c" in w[1:]:
            return words[i + 1] if i + 1 < len(words) else None
        if not w.startswith("-"):
            return None  # bash script.sh: a file, not inline code
    return None


# ---- git ----------------------------------------------------------------

_SHARED_BRANCHES = {"main", "master", "develop", "trunk"}
_HOOK_BYPASS_SUBCOMMANDS = {"commit", "push", "merge", "cherry-pick", "rebase", "am"}
_GIT_GLOBAL_VALUE_FLAGS = {
    "-c",
    "-C",
    "--git-dir",
    "--work-tree",
    "--namespace",
    "--super-prefix",
    "--exec-path",
    "--config-env",
}
_COMMIT_VALUE_LONG = {
    "-m",
    "--message",
    "-F",
    "--file",
    "-C",
    "--reuse-message",
    "-c",
    "--reedit-message",
    "--author",
    "--date",
    "--template",
    "--fixup",
    "--squash",
    "--pathspec-from-file",
    "--trailer",
    "--cleanup",
}
_COMMIT_VALUE_SHORT = set("mFCct")
_COMMIT_OPTIONAL_VALUE_SHORT = set("uS")


def _git_split(words: list[str]) -> tuple[list[str], str | None, list[str]]:
    """Return (global option words, subcommand, rest) for a git invocation."""
    i = 1
    while i < len(words):
        w = words[i]
        if w in _GIT_GLOBAL_VALUE_FLAGS:
            i += 2
            continue
        if w.startswith("-"):
            i += 1
            continue
        return words[1:i], w.lower(), words[i + 1 :]
    return words[1:], None, []


def _is_no_verify_long(w: str) -> bool:
    # git accepts any unambiguous prefix; --no-ver is ambiguous with --no-verbose.
    return len(w) >= len("--no-v") and "--no-verify".startswith(w)


def _commit_short_cluster_has_n(w: str) -> bool:
    for ch in w[1:]:
        if ch == "n":
            return True
        if ch in _COMMIT_VALUE_SHORT or ch in _COMMIT_OPTIONAL_VALUE_SHORT:
            return False  # the rest of the cluster is that option's value
    return False


def _has_hook_bypass(sub: str, rest: list[str]) -> bool:
    skip = False
    for w in rest:
        if skip:
            skip = False
            continue
        if w == "--":
            return False
        if sub == "commit":
            if w in _COMMIT_VALUE_LONG:
                skip = True
                continue
            if w.startswith("--") and "=" in w:
                continue
            if w.startswith("-") and not w.startswith("--") and len(w) > 1:
                if _commit_short_cluster_has_n(w):
                    return True
                last = w[-1]
                if last in _COMMIT_VALUE_SHORT and not any(
                    ch in _COMMIT_VALUE_SHORT | _COMMIT_OPTIONAL_VALUE_SHORT for ch in w[1:-1]
                ):
                    skip = True
                continue
        if _is_no_verify_long(w):
            return True
    return False


def _hooks_path_override(global_opts: list[str]) -> bool:
    for i, w in enumerate(global_opts):
        if w == "-c" and i + 1 < len(global_opts) and global_opts[i + 1].lower().startswith("core.hookspath="):
            return True
        if w.lower().startswith("-ccore.hookspath="):
            return True
    return False


def _short_flags(rest: Iterable[str]) -> str:
    return "".join(w[1:] for w in rest if w.startswith("-") and not w.startswith("--"))


def _refspec_destination(refspec: str) -> tuple[str, bool]:
    """(branch name, is_force_marked) for one push refspec."""
    force = refspec.startswith("+")
    spec = refspec[1:] if force else refspec
    dst = spec.split(":", 1)[1] if ":" in spec else spec
    if dst.startswith("refs/heads/"):
        dst = dst[len("refs/heads/") :]
    return dst, force


def _classify_push(rest: list[str]) -> Finding | None:
    value_flags = {"-o", "--push-option", "--receive-pack", "--exec", "--repo"}
    positional: list[str] = []
    force = lease = delete = mirror = False
    remote_via_flag = False
    skip = False
    for w in rest:
        if skip:
            skip = False
            continue
        if w in value_flags:
            remote_via_flag = remote_via_flag or w == "--repo"
            skip = True
            continue
        if w.startswith("--repo="):
            remote_via_flag = True
            continue
        if w == "--force" or w.startswith("--force="):
            force = True
        elif w == "--force-with-lease" or w.startswith("--force-with-lease=") or w == "--force-if-includes":
            lease = True
        elif w in ("--delete",):
            delete = True
        elif w == "--mirror":
            mirror = True
        elif w.startswith("-") and not w.startswith("--"):
            if "f" in w[1:]:
                force = True
            if "d" in w[1:]:
                delete = True
        elif not w.startswith("-"):
            positional.append(w)
    refspecs = positional if remote_via_flag else positional[1:]
    if mirror:
        return Finding(BLOCK, "git push --mirror overwrites every ref on the remote")
    shared_hit = False
    plus_force = False
    for spec in refspecs:
        dst, marked = _refspec_destination(spec)
        plus_force = plus_force or marked
        if dst in _SHARED_BRANCHES:
            shared_hit = True
        if (spec.startswith(":") or delete) and dst in _SHARED_BRANCHES:
            return Finding(BLOCK, f"git push deletes the shared branch {dst}")
    if (force or plus_force or lease) and shared_hit:
        return Finding(BLOCK, "force-pushing main/master/develop/trunk rewrites history other clones build on")
    if force or plus_force:
        return Finding(ASK, "git push --force overwrites remote history; prefer --force-with-lease")
    if delete:
        return Finding(ASK, "git push --delete removes a remote branch")
    return None


def classify_git(words: list[str]) -> list[Finding]:
    global_opts, sub, rest = _git_split(words)
    findings: list[Finding] = []
    if sub is None:
        return findings
    if _hooks_path_override(global_opts):
        findings.append(Finding(BLOCK, "overriding core.hooksPath skips the repository's git hooks"))
    if sub in _HOOK_BYPASS_SUBCOMMANDS and _has_hook_bypass(sub, rest):
        reason = f"git {sub} --no-verify skips the repository's git hooks; fix what they report instead"
        findings.append(Finding(BLOCK, reason))
    flags = _short_flags(rest)
    if sub == "push":
        f = _classify_push(rest)
        if f:
            findings.append(f)
    elif sub == "reset" and "--hard" in rest:
        findings.append(Finding(ASK, "git reset --hard discards uncommitted work"))
    elif sub == "checkout" and ("--" in rest or "." in rest or "--force" in rest or "f" in flags):
        findings.append(Finding(ASK, "git checkout over paths or with --force discards local changes"))
    elif sub == "clean" and ("--force" in rest or "f" in flags) and not ("n" in flags or "--dry-run" in rest):
        findings.append(Finding(ASK, "git clean -f deletes untracked files"))
    elif sub == "restore":
        staged = "--staged" in rest or "S" in flags
        worktree = "--worktree" in rest or "W" in flags
        if worktree or not staged:
            findings.append(Finding(ASK, "git restore of the worktree discards local changes"))
    elif sub == "switch" and ("--discard-changes" in rest or "--force" in rest or "f" in flags or "C" in flags):
        findings.append(Finding(ASK, "git switch --force/-C discards local changes or resets a branch"))
    elif sub == "branch":
        delete = "--delete" in rest or "d" in flags
        force = "--force" in rest or "f" in flags
        if "D" in flags or (delete and force):
            findings.append(Finding(ASK, "git branch -D deletes a branch even if it is unmerged"))
    elif sub == "stash" and rest[:1] and rest[0] in ("drop", "clear"):
        findings.append(Finding(ASK, f"git stash {rest[0]} permanently discards stashed work"))
    elif sub == "reflog" and rest[:1] and rest[0] in ("expire", "delete"):
        findings.append(Finding(ASK, "rewriting the reflog removes the recovery trail"))
    elif sub == "update-ref" and ("-d" in rest or "--delete" in rest):
        findings.append(Finding(ASK, "git update-ref -d deletes a ref"))
    elif sub in ("filter-branch", "filter-repo"):
        findings.append(Finding(ASK, f"git {sub} rewrites history"))
    return findings


# ---- rm -------------------------------------------------------------------

_CRITICAL_TARGETS = {
    "/",
    "/*",
    "~",
    "~/",
    "~/*",
    "$HOME",
    "$HOME/",
    "$HOME/*",
    "${HOME}",
    "${HOME}/",
    "${HOME}/*",
    ".",
    "./",
    "./*",
    "..",
    "../",
    "../*",
    "*",
}
_SYSTEM_DIRS = {
    "/applications",
    "/bin",
    "/etc",
    "/library",
    "/opt",
    "/private",
    "/sbin",
    "/system",
    "/usr",
    "/users",
    "/var",
    "/volumes",
    "/home",
    "/nix",
}
# Relative paths whose first component is one of these are regenerable artifacts.
_ARTIFACT_DIRS = {
    "build",
    "builds",
    "dist",
    "out",
    "target",
    "node_modules",
    "coverage",
    "htmlcov",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    ".next",
    ".turbo",
    ".parcel-cache",
    ".tox",
    ".nox",
    ".eggs",
    "tmp",
    ".tmp",
    ".gradle",
    "bazel-bin",
    "bazel-out",
    "bazel-testlogs",
    ".hypothesis",
    ".benchmarks",
    "site",
    "_build",
}
_TEMP_PREFIXES = ("/tmp/", "/private/tmp/", "/var/folders/", "/private/var/folders/", "$TMPDIR/", "${TMPDIR}/")


def _is_critical_rm_target(target: str) -> bool:
    t = target.rstrip("/") or "/"
    if target in _CRITICAL_TARGETS or t in _CRITICAL_TARGETS:
        return True
    lowered = posixpath.normpath(t).lower() if t.startswith("/") else t.lower()
    if lowered in _SYSTEM_DIRS:
        return True
    return lowered.startswith("/users/") and lowered.count("/") == 2  # someone's home directory


def _is_artifact_rm_target(target: str) -> bool:
    if target.startswith(_TEMP_PREFIXES):
        return True
    if target.startswith("/") or target.startswith("~") or target.startswith("$"):
        return False
    norm = posixpath.normpath(target)
    if norm.startswith(".."):
        return False
    first = norm.split("/", 1)[0]
    return first in _ARTIFACT_DIRS or first.startswith("cmake-build-")


def classify_rm(words: list[str]) -> list[Finding]:
    recursive = force = False
    targets: list[str] = []
    end_of_opts = False
    for w in words[1:]:
        if not end_of_opts and w == "--":
            end_of_opts = True
            continue
        if not end_of_opts and w.startswith("--"):
            recursive = recursive or w == "--recursive"
            force = force or w == "--force"
            continue
        if not end_of_opts and w.startswith("-") and len(w) > 1:
            recursive = recursive or "r" in w or "R" in w
            force = force or "f" in w
            continue
        targets.append(w)
    if not recursive:
        return []
    critical = [t for t in targets if _is_critical_rm_target(t)]
    if critical:
        return [Finding(BLOCK, f"recursive rm of a critical path ({', '.join(critical)})")]
    if not force:
        return []
    if targets and all(_is_artifact_rm_target(t) for t in targets):
        return []
    return [Finding(ASK, f"rm -rf of {' '.join(targets) or 'unspecified paths'}")]


# ---- SQL, find, disks -------------------------------------------------------

_SQL_DROP = re.compile(r"\b(drop\s+(table|database|schema|index|view)|truncate(\s+table)?\s+\w)", re.I)
_SQL_DELETE = re.compile(r"\bdelete\s+from\b(?![^;]*\bwhere\b)", re.I)


def classify_sql_text(sql: str) -> list[Finding]:
    if _SQL_DROP.search(sql):
        return [Finding(ASK, "destructive SQL (DROP/TRUNCATE)")]
    if _SQL_DELETE.search(sql):
        return [Finding(ASK, "DELETE without WHERE removes every row")]
    return []


def classify_find(words: list[str], depth: int) -> list[Finding]:
    findings: list[Finding] = []
    for i, w in enumerate(words):
        if w in ("-exec", "-execdir", "-ok", "-okdir"):
            inner: list[str] = []
            for t in words[i + 1 :]:
                if t in (";", "\\;", "+"):
                    break
                inner.append(t)
            if not inner:
                continue
            base = _base(inner[0])
            if base in ("rm", "rmdir", "unlink", "shred", "srm"):
                findings.append(Finding(ASK, f"find {w} {base} deletes every match"))
            else:
                findings.extend(classify_words(inner, depth + 1))
    return findings


def classify_words(words: list[str], depth: int = 0) -> list[Finding]:
    words = unwrap(words)
    if not words or depth > MAX_DEPTH:
        return []
    base = _base(words[0])
    if base in _SHELLS:
        script = _shell_script_arg(words)
        return classify_command(script, depth + 1) if script else []
    if base == "eval":
        return classify_command(" ".join(words[1:]), depth + 1)
    if base == "git":
        return classify_git(words)
    if base == "rm":
        return classify_rm(words)
    if base == "find":
        return classify_find(words, depth)
    if base in _SQL_CLIENTS:
        return classify_sql_text(" ".join(words[1:]))
    if base == "dd" and any(w.startswith("of=") for w in words[1:]):
        return [Finding(ASK, "dd of= overwrites the target raw")]
    erasing = ("erase", "partition", "zerodisk", "secureerase")
    if base == "diskutil" and len(words) > 1 and words[1].lower().startswith(erasing):
        return [Finding(BLOCK, f"diskutil {words[1]} erases a disk")]
    if base.startswith("mkfs"):
        return [Finding(BLOCK, "mkfs formats a filesystem")]
    return []


def classify_command(command: str, depth: int = 0) -> list[Finding]:
    if depth > MAX_DEPTH or not command.strip():
        return []
    lexed = lex(command)
    findings: list[Finding] = []
    for words in lexed.segments:
        findings.extend(classify_words(words, depth))
    for body in lexed.substitutions:
        findings.extend(classify_command(body, depth + 1))
    for doc in lexed.heredocs:
        owner = lexed.segments[doc.segment_index] if doc.segment_index < len(lexed.segments) else []
        owner = unwrap(owner)
        base = _base(owner[0]) if owner else ""
        if base in _SHELLS or base == "eval":
            findings.extend(classify_command(doc.body, depth + 1))
        elif base in _SQL_CLIENTS:
            findings.extend(classify_sql_text(doc.body))
    return findings


def worst(findings: Iterable[Finding]) -> Finding | None:
    best: Finding | None = None
    for f in findings:
        if best is None or _SEVERITY[f.level] > _SEVERITY[best.level]:
            best = f
    return best


# --------------------------------------------------------------------------
# Config protection
# --------------------------------------------------------------------------

PROTECTED_CONFIGS = frozenset(
    {
        # C / C++
        ".clang-format",
        "_clang-format",
        ".clang-tidy",
        # Python
        ".ruff.toml",
        "ruff.toml",
        ".flake8",
        "mypy.ini",
        ".mypy.ini",
        "pyrightconfig.json",
        ".pylintrc",
        "pylintrc",
        ".bandit",
        # JS / TS
        ".eslintrc",
        ".eslintrc.js",
        ".eslintrc.cjs",
        ".eslintrc.json",
        ".eslintrc.yml",
        ".eslintrc.yaml",
        "eslint.config.js",
        "eslint.config.mjs",
        "eslint.config.cjs",
        "eslint.config.ts",
        "eslint.config.mts",
        "eslint.config.cts",
        ".prettierrc",
        ".prettierrc.js",
        ".prettierrc.cjs",
        ".prettierrc.json",
        ".prettierrc.yml",
        ".prettierrc.yaml",
        "prettier.config.js",
        "prettier.config.cjs",
        "prettier.config.mjs",
        "biome.json",
        "biome.jsonc",
        ".stylelintrc",
        ".stylelintrc.json",
        ".stylelintrc.yml",
        # Rust / Go / Swift
        "rustfmt.toml",
        ".rustfmt.toml",
        "clippy.toml",
        ".golangci.yml",
        ".golangci.yaml",
        ".swiftlint.yml",
        # Shell, Markdown, YAML, editors
        ".shellcheckrc",
        ".markdownlint.json",
        ".markdownlint.yaml",
        ".markdownlintrc",
        ".yamllint",
        ".yamllint.yml",
        ".yamllint.yaml",
        ".editorconfig",
        # Gates
        ".pre-commit-config.yaml",
        "lefthook.yml",
        "lefthook.yaml",
        ".lefthook.yml",
        ".lefthook.yaml",
        ".no-mistakes.yaml",
        ".no-mistakes.yml",
    }
)


def protected_config(file_path: str) -> str | None:
    """Basename if file_path is an existing protected config; None otherwise (new files are fine)."""
    if not file_path:
        return None
    name = posixpath.basename(file_path.replace("\\", "/"))
    if name.lower() not in PROTECTED_CONFIGS:
        return None
    try:
        os.lstat(file_path)
    except FileNotFoundError:
        return None  # bootstrapping a config into a project that has none
    except OSError:
        pass  # unreadable: fail closed, treat as present
    return name


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def decision(level: str, reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": level,
            "permissionDecisionReason": reason,
        }
    }


def decide_bash(command: str, present: bool) -> dict | None:
    try:
        finding = worst(classify_command(command))
    except ValueError:
        return None  # unparseable (an unterminated quote fails in bash too)
    if finding is None:
        return None
    if finding.level == BLOCK:
        return decision(
            "deny",
            f"guard: blocked - {finding.reason}. Do not work around this guard. "
            "If it is truly intended, ask the user to run it themselves with the ! prefix.",
        )
    if present:
        return decision("ask", f"guard: {finding.reason}.")
    return None


def decide_edit(file_path: str, present: bool) -> dict | None:
    name = protected_config(file_path)
    if name is None:
        return None
    if present:
        return decision(
            "ask",
            f"guard: {name} is an existing lint/format/gate config. "
            "Approve only if you asked for this config change; otherwise the fix belongs in the code.",
        )
    return decision(
        "deny",
        f"guard: {name} is an existing lint/format/gate config and this run is unattended. "
        "Fix the code so the check passes instead of weakening the check. "
        "If the task really requires changing this config, stop and report it for a human to approve.",
    )


def main(argv: list[str], stdin: str, env: Mapping[str, str]) -> str:
    """Return the text to print on stdout (empty for allow)."""
    if len(argv) != 2 or argv[1] not in ("bash", "edit"):
        raise SystemExit("usage: guard.py bash|edit  (reads PreToolUse JSON on stdin)")
    if env.get("CLAUDE_GUARD_DISABLE") == "1":
        return ""
    try:
        payload = json.loads(stdin) if stdin.strip() else {}
    except json.JSONDecodeError:
        return ""
    tool_input = payload.get("tool_input") or {}
    present = human_present(env)
    if argv[1] == "bash":
        result = decide_bash(str(tool_input.get("command") or ""), present)
    else:
        result = decide_edit(str(tool_input.get("file_path") or ""), present)
    return json.dumps(result) if result else ""


if __name__ == "__main__":
    try:
        out = main(sys.argv, sys.stdin.read(), os.environ)
    except SystemExit:
        raise
    except Exception as exc:  # fail open: a guard bug must never block work
        print(f"guard: internal error, allowing: {exc!r}", file=sys.stderr)
        sys.exit(0)
    if out:
        print(out)
