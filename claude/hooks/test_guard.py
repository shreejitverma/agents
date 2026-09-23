"""Tests for guard.py. Run: python3 -m unittest discover -s claude/hooks -v"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import guard  # noqa: E402

GUARD = Path(__file__).resolve().parent / "guard.py"
SETTINGS = Path(__file__).resolve().parent.parent / "settings.json"
ATTENDED = {"CLAUDE_CODE_SESSION_ATTENDED": "1"}
UNATTENDED = {"CLAUDE_CODE_SESSION_ATTENDED": "0"}


def level(command: str) -> str | None:
    finding = guard.worst(guard.classify_command(command))
    return finding.level if finding else None


BLOCKED = [
    # git hook bypass
    "git commit --no-verify -m 'x'",
    "git commit -m 'x' --no-verify",
    "git commit -nm 'x'",
    "git commit -an -m x",
    "git commit --no-veri -m x",
    "git push --no-verify origin feat",
    "git merge --no-verify feat",
    "git rebase --no-verify main",
    "git -c core.hooksPath=/dev/null commit -m x",
    "git -c core.hooksPath=/dev/null push",
    "/usr/bin/git commit --no-verify",
    # shared branches
    "git push --force origin main",
    "git push -f origin master",
    "git push origin +main",
    "git push origin HEAD:main --force",
    "git push --force-with-lease origin main",
    "git push origin :main",
    "git push origin --delete main",
    "git push --mirror origin",
    # critical rm
    "rm -rf /",
    "rm -rf ~",
    "rm -rf ~/",
    "rm -rf $HOME",
    'rm -rf "$HOME"',
    "rm -rf /*",
    "rm -rf ..",
    "rm -rf .",
    "rm -fr /usr",
    "rm -r --force /Users/someone",
    "sudo rm -rf /",
    "rm -rf -- /",
    # disks
    "diskutil eraseDisk APFS X disk4",
    "mkfs.ext4 /dev/sdb1",
    # evasion through wrappers and nesting
    "bash -c 'git push --force origin main'",
    'sh -lc "rm -rf ~"',
    "eval 'git commit --no-verify -m x'",
    "echo $(git push -f origin main)",
    "echo `rm -rf /`",
    "cd repo && git commit --no-verify -m x",
    "true; git push --force origin main",
    "(cd x; git push origin +main)",
    "env GIT_TRACE=1 git commit --no-verify",
    "FOO=1 git commit -n -m x",
    "timeout 60 git push --force origin main",
    "nohup rm -rf / &",
    "echo hi # comment\ngit commit --no-verify -m x",
    "bash <<'EOF'\ngit push --force origin main\nEOF",
    'git commit -m "$(date)" --no-verify',
    # redirections must not hide the next command
    "ls 2>&1 | git commit --no-verify",
    # heredoc with an apostrophe inside a command substitution
    "git commit --no-verify -m \"$(cat <<'EOF'\nfix: don't crash\nEOF\n)\"",
    # shell options that take a value, and heredocs piped into a shell
    "bash -o pipefail -c 'rm -rf ~'",
    "bash -eo pipefail -c 'rm -rf ~'",
    "cat <<'EOF' | bash\ngit push --force origin main\nEOF",
    "cat <<'EOF' | sudo bash -s\ngit push --force origin main\nEOF",
    # empty words and arithmetic shifts inside multi-line substitutions
    "bash '' ; git commit --no-verify -m x",
    'bash "" -c x; git push --force origin main',
    "x=$(\necho $((1<<3))\n) ; git commit --no-verify",
]

ASKED = [
    "git reset --hard",
    "git reset --hard origin/main",
    "git -C sub reset --hard HEAD~1",
    "git checkout -- file.py",
    "git checkout .",
    "git checkout -f main",
    "git clean -fd",
    "git clean -fdx",
    "git restore file.py",
    "git restore --worktree --staged file.py",
    "git switch -C feat origin/feat",
    "git switch --discard-changes main",
    "git branch -D feat",
    "git branch --delete --force feat",
    "git stash drop",
    "git stash clear",
    "git reflog expire --expire=now --all",
    "git update-ref -d refs/heads/x",
    "git push --force",
    "git push -f origin feat",
    "git push origin +feat",
    "git push origin --delete feat",
    "git filter-branch --tree-filter x HEAD",
    "rm -rf src",
    "rm -rf $HOME/github/foo",
    "rm -rf build src",
    "echo a | xargs rm -rf",
    "find . -name '*.o' -exec rm {} \\;",
    "find . -type d -execdir rm -rf {} +",
    "psql -c 'DROP TABLE users'",
    "psql -c 'truncate table trades'",
    "sqlite3 db.sqlite 'DELETE FROM fills'",
    "psql <<'SQL'\ndrop table x;\nSQL",
    "dd if=/dev/zero of=disk.img bs=1m count=1",
    "for d in a b; do rm -rf $d; done",
    "exec 3>&- ; rm -rf src",
    "cmd 2>&- && git reset --hard",
    "cmd <&- ; git reset --hard",
    "cmd 3>&1- ; git reset --hard",
    "cat <<'SQL' | psql\ndrop table x;\nSQL",
]

ALLOWED = [
    "git status",
    "git commit -m 'fix -n handling'",
    "git commit -m 'mention --no-verify in docs'",
    "git commit -am 'msg'",
    'git commit -m"-n"',
    "git commit -F msg.txt",
    "git push",
    "git push -u origin feat",
    "git push -n origin main",
    "git push --force-with-lease origin feat",
    "git push origin feat:feat",
    "git reset HEAD file",
    "git reset --soft HEAD~1",
    "git checkout -b feat",
    "git checkout main",
    "git switch -c feat",
    "git clean -n",
    "git clean -fdn",
    "git restore --staged file.py",
    "git branch -d merged",
    "git stash",
    "git stash pop",
    "git log --oneline | head",
    "rm file.txt",
    "rm -f file.txt",
    "rm -r empty_dir",
    "rm -rf build",
    "rm -rf build/ dist/ .pytest_cache",
    "rm -rf ./build",
    "rm -rf cmake-build-debug",
    "rm -rf node_modules",
    "rm -rf /tmp/foo",
    "rm -rf /private/tmp/claude-501/x/scratchpad/out",
    'rm -rf "$TMPDIR/x"',
    "echo 'rm -rf /'",
    'echo "git push --force origin main"',
    "grep -rn 'git commit --no-verify' .",
    "cat <<'EOF' > notes.md\nrm -rf /\ngit push --force origin main\nEOF",
    "cat <<'EOF' | bash script.sh\ngit push --force origin main\nEOF",
    "git commit -m \"$(cat <<'EOF'\nfix: don't crash\nEOF\n)\"",
    'echo "$(cat <<-EOF\n\tit\'s fine\n\tEOF\n)"',
    "python3 - <<'EOF'\nimport os\nos.system('echo')\nEOF",
    "find . -name '*.pyc' -print",
    "psql -c 'select * from trades'",
    "sqlite3 db 'delete from t where id = 1'",
    "dd if=disk.img bs=1m count=1",
    "ls 2>/dev/null",
    "make -j8 2>&1 | tee build.log",
    "cmake --build build && ctest --test-dir build",
    "echo $((1 + 2))",
    "echo ${HOME}",
    "",
    "   ",
]


class ClassifierTest(unittest.TestCase):
    def test_blocked(self) -> None:
        for command in BLOCKED:
            with self.subTest(command=command):
                self.assertEqual(level(command), guard.BLOCK)

    def test_asked(self) -> None:
        for command in ASKED:
            with self.subTest(command=command):
                self.assertEqual(level(command), guard.ASK)

    def test_allowed(self) -> None:
        for command in ALLOWED:
            with self.subTest(command=command):
                self.assertIsNone(level(command))

    def test_unterminated_quote_fails_open(self) -> None:
        self.assertIsNone(guard.decide_bash("echo 'unterminated", present=True))
        self.assertIsNone(guard.decide_bash("git reset --hard; echo 'unterminated", present=True))


class UnparsedFallbackTest(unittest.TestCase):
    DENIED = [
        "bash '' ; git commit --no-verify -m x",
        "echo 'unterminated ; git push --force origin main",
        'git commit -nm "unterminated',
        "git -c core.hooksPath=/dev/null commit -m 'x",
        'echo "$(git push origin +main',
        "echo 'x' && git push --mirror origin 'y",
        "git push origin --delete master 'y",
        "echo 'x; rm -rf ~",
        "echo 'x; sudo rm -fr /usr",
    ]
    ALLOWED = [
        "echo 'unterminated",
        "echo 'x; git push --force origin feat",
        "echo 'x; rm -rf src",
        "echo 'x; git reset --hard",
        "git commit -m 'unterminated",
    ]

    def test_markers(self) -> None:
        for command in self.DENIED:
            with self.subTest(command=command):
                finding = guard.unparsed_block_finding(command)
                self.assertIsNotNone(finding)
                self.assertEqual(finding.level, guard.BLOCK)

    def test_no_marker(self) -> None:
        for command in self.ALLOWED:
            with self.subTest(command=command):
                self.assertIsNone(guard.unparsed_block_finding(command))

    def test_decide_bash_denies_unparseable_marker(self) -> None:
        for present in (True, False):
            for command in self.DENIED:
                with self.subTest(command=command, present=present):
                    d = guard.decide_bash(command, present)["hookSpecificOutput"]
                    self.assertEqual(d["permissionDecision"], "deny")

    def test_unparseable_reason(self) -> None:
        d = guard.decide_bash("echo 'unterminated ; git push --force origin main", True)["hookSpecificOutput"]
        self.assertIn("could not be parsed", d["permissionDecisionReason"])
        self.assertIn("main", d["permissionDecisionReason"])

    def test_decide_bash_allows_unparseable_without_marker(self) -> None:
        for command in self.ALLOWED:
            with self.subTest(command=command):
                self.assertIsNone(guard.decide_bash(command, present=True))


class LexerTest(unittest.TestCase):
    def test_segments_and_redirections(self) -> None:
        lexed = guard.lex("a 1 > out.txt 2>&1; b | c && d\ne")
        self.assertEqual(lexed.segments, [["a", "1"], ["b"], ["c"], ["d"], ["e"]])

    def test_quotes_removed(self) -> None:
        self.assertEqual(guard.lex("""echo 'a b' "c d" e\\ f""").segments, [["echo", "a b", "c d", "e f"]])

    def test_substitutions_collected(self) -> None:
        lexed = guard.lex('echo "$(inner one)" `inner two` <(inner three)')
        self.assertEqual(lexed.substitutions, ["inner one", "inner two", "inner three"])

    def test_heredoc_body_separated(self) -> None:
        lexed = guard.lex("cat <<EOF >x\nbody line\nEOF\nnext")
        self.assertEqual(lexed.segments, [["cat"], ["next"]])
        self.assertEqual(lexed.heredocs[0].body, "body line")

    def test_fd_close_keeps_next_word(self) -> None:
        self.assertEqual(guard.lex("exec 3>&- ; rm x").segments, [["exec"], ["rm", "x"]])
        self.assertEqual(guard.lex("a 2>&1 b").segments, [["a", "b"]])

    def test_dangling_redirection_does_not_cross_segments(self) -> None:
        self.assertEqual(guard.lex("a > ; b c").segments, [["a"], ["b", "c"]])

    def test_heredoc_inside_substitution(self) -> None:
        lexed = guard.lex("echo \"$(cat <<'EOF'\nit's (\nEOF\n)\" done")
        self.assertEqual(lexed.segments, [["echo", "$(...)", "done"]])
        self.assertEqual(lexed.substitutions, ["cat <<'EOF'\nit's (\nEOF\n"])


class PresenceTest(unittest.TestCase):
    def test_attended(self) -> None:
        self.assertTrue(guard.human_present(ATTENDED))

    def test_print_mode(self) -> None:
        self.assertFalse(guard.human_present(UNATTENDED))

    def test_firstmate_crewmate(self) -> None:
        self.assertFalse(guard.human_present({**ATTENDED, "FM_TASK_ID": "t1"}))

    def test_legacy_fallback(self) -> None:
        self.assertTrue(guard.human_present({"CLAUDE_CODE_ENTRYPOINT": "cli"}))
        self.assertFalse(guard.human_present({"CLAUDE_CODE_ENTRYPOINT": "sdk-cli"}))


class DecisionTest(unittest.TestCase):
    def decide(self, mode: str, tool_input: dict, env: dict) -> dict | None:
        out = guard.main(["guard.py", mode], json.dumps({"tool_input": tool_input}), env)
        return json.loads(out)["hookSpecificOutput"] if out else None

    def test_block_denies_even_unattended(self) -> None:
        for env in (ATTENDED, UNATTENDED):
            d = self.decide("bash", {"command": "git commit --no-verify"}, env)
            self.assertEqual(d["permissionDecision"], "deny")
            self.assertEqual(d["hookEventName"], "PreToolUse")

    def test_destructive_asks_only_when_attended(self) -> None:
        d = self.decide("bash", {"command": "git reset --hard"}, ATTENDED)
        self.assertEqual(d["permissionDecision"], "ask")
        self.assertIsNone(self.decide("bash", {"command": "git reset --hard"}, UNATTENDED))

    def test_disable_switch(self) -> None:
        env = {**ATTENDED, "CLAUDE_GUARD_DISABLE": "1"}
        self.assertIsNone(self.decide("bash", {"command": "rm -rf /"}, env))

    def test_bad_json_allows(self) -> None:
        self.assertEqual(guard.main(["guard.py", "bash"], "{not json", ATTENDED), "")

    def test_config_edit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            existing = os.path.join(tmp, ".clang-tidy")
            Path(existing).write_text("Checks: '*'\n")
            fresh = os.path.join(tmp, "ruff.toml")
            source = os.path.join(tmp, "main.cpp")
            Path(source).write_text("int main() {}\n")
            upper = os.path.join(tmp, "MYPY.INI")
            Path(upper).write_text("[mypy]\n")

            self.assertEqual(self.decide("edit", {"file_path": existing}, ATTENDED)["permissionDecision"], "ask")
            self.assertEqual(self.decide("edit", {"file_path": existing}, UNATTENDED)["permissionDecision"], "deny")
            self.assertEqual(self.decide("edit", {"file_path": upper}, UNATTENDED)["permissionDecision"], "deny")
            self.assertIsNone(self.decide("edit", {"file_path": fresh}, UNATTENDED))
            self.assertIsNone(self.decide("edit", {"file_path": source}, UNATTENDED))
            self.assertIsNone(self.decide("edit", {}, UNATTENDED))

    def test_dangling_symlink_counts_as_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            link = os.path.join(tmp, ".no-mistakes.yaml")
            os.symlink(os.path.join(tmp, "missing"), link)
            self.assertEqual(self.decide("edit", {"file_path": link}, UNATTENDED)["permissionDecision"], "deny")


class ProcessTest(unittest.TestCase):
    """End to end through the real interpreter, as Claude Code invokes it."""

    def run_guard(self, mode: str, payload: str, extra_env: dict) -> subprocess.CompletedProcess:
        env = {k: v for k, v in os.environ.items() if k not in ("FM_TASK_ID", "CLAUDE_GUARD_DISABLE")}
        env.update(extra_env)
        return subprocess.run(
            [sys.executable, str(GUARD), mode],
            input=payload,
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
            check=False,
        )

    def test_deny_json_on_stdout(self) -> None:
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git push -f origin main"}})
        proc = self.run_guard("bash", payload, UNATTENDED)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_allow_is_silent(self) -> None:
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        proc = self.run_guard("bash", payload, ATTENDED)
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, "", ""))

    def test_usage_error(self) -> None:
        proc = self.run_guard("nope", "{}", ATTENDED)
        self.assertNotEqual(proc.returncode, 0)


class SettingsHookTest(unittest.TestCase):
    """The exact hook commands from settings.json, run through /bin/sh as Claude Code does."""

    def hook_commands(self) -> dict[str, str]:
        entries = json.loads(SETTINGS.read_text())["hooks"]["PreToolUse"]
        return {entry["matcher"]: entry["hooks"][0]["command"] for entry in entries}

    def run_hook(self, command: str, home: str, tool_input: dict) -> subprocess.CompletedProcess:
        env = {k: v for k, v in os.environ.items() if k not in ("FM_TASK_ID", "CLAUDE_GUARD_DISABLE")}
        env.update(UNATTENDED, HOME=home)
        return subprocess.run(
            ["/bin/sh", "-c", command],
            input=json.dumps({"tool_input": tool_input}),
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
            check=False,
        )

    def test_missing_script_allows(self) -> None:
        commands = self.hook_commands()
        self.assertEqual(set(commands), {"Bash", "Write|Edit|MultiEdit"})
        with tempfile.TemporaryDirectory() as home:
            for command in commands.values():
                with self.subTest(command=command):
                    proc = self.run_hook(command, home, {"command": "git push -f origin main"})
                    self.assertEqual((proc.returncode, proc.stdout), (0, ""))

    def test_installed_script_runs(self) -> None:
        commands = self.hook_commands()
        with tempfile.TemporaryDirectory() as home:
            hooks = Path(home, "github", "agents", "claude", "hooks")
            hooks.mkdir(parents=True)
            (hooks / "guard.py").symlink_to(GUARD)
            config = Path(home, ".clang-tidy")
            config.write_text("Checks: '*'\n")
            bash = self.run_hook(commands["Bash"], home, {"command": "git push -f origin main"})
            edit = self.run_hook(commands["Write|Edit|MultiEdit"], home, {"file_path": str(config)})
            for proc in (bash, edit):
                self.assertEqual(proc.returncode, 0)
                self.assertEqual(json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
