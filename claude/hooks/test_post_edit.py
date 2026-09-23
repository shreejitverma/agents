"""Tests for post_edit.py. Run: python3 -m unittest discover -s claude/hooks -v"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import post_edit  # noqa: E402

HOOK = Path(__file__).resolve().parent / "post_edit.py"
SETTINGS = Path(__file__).resolve().parent.parent / "settings.json"

# Stub tools on PATH: they fail when the file contains the marker, so the
# decision logic is tested without depending on the real tools' versions.
RUFF_STUB = """#!/bin/sh
f=""; for a in "$@"; do f="$a"; done
case "$1" in
  check)  if grep -q LINT "$f"; then echo "$f:1:1: F401 unused import"; exit 1; fi ;;
  format) if grep -q FMT "$f"; then exit 1; fi ;;
esac
exit 0
"""
CLANG_FORMAT_STUB = """#!/bin/sh
f=""; for a in "$@"; do f="$a"; done
if grep -q FMT "$f"; then
  echo "$f:1:5: error: code should be clang-formatted [-Wclang-format-violations]" >&2
  exit 1
fi
exit 0
"""
CLANG_FORMAT_BAD_CONFIG_STUB = """#!/bin/sh
echo "YAML:3:1: error: unknown key 'InsertNewlineAtEOF'" >&2
echo "Error reading $PWD/.clang-format: Invalid argument" >&2
exit 1
"""
SLEEP_STUB = "#!/bin/sh\nsleep 30\n"
LONG_RUFF_STUB = """#!/bin/sh
[ "$1" = check ] || exit 0
for i in $(seq 100); do echo "a.py:$i:1: E501"; done
exit 1
"""


class PostEditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.repo = self.tmp / "repo"
        (self.repo / ".git").mkdir(parents=True)
        self.old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{self.bin}{os.pathsep}/usr/bin{os.pathsep}/bin"
        self.addCleanup(os.environ.__setitem__, "PATH", self.old_path)

    def stub(self, name: str, body: str) -> None:
        p = self.bin / name
        p.write_text(body)
        p.chmod(0o755)

    def write(self, rel: str, text: str) -> Path:
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def fb(self, path: Path, env: dict[str, str] | None = None) -> str:
        return post_edit.feedback({"tool_input": {"file_path": str(path)}}, env or {})

    # -- Python ----------------------------------------------------------

    def test_python_without_ruff_config_is_silent(self) -> None:
        self.stub("ruff", RUFF_STUB)
        self.assertEqual(self.fb(self.write("a.py", "LINT FMT\n")), "")

    def test_python_lint_and_format_findings_reported(self) -> None:
        self.stub("ruff", RUFF_STUB)
        self.write("ruff.toml", "")
        out = self.fb(self.write("pkg/a.py", "LINT FMT\n"))
        self.assertIn("ruff check found problems", out)
        self.assertIn("F401", out)
        self.assertIn("ruff format would reformat", out)

    def test_clean_python_is_silent(self) -> None:
        self.stub("ruff", RUFF_STUB)
        self.write("ruff.toml", "")
        self.assertEqual(self.fb(self.write("a.py", "x = 1\n")), "")

    def test_pyproject_tool_ruff_counts_as_config(self) -> None:
        self.stub("ruff", RUFF_STUB)
        self.write("pyproject.toml", "[project]\nname='x'\n\n[tool.ruff.lint]\nselect=['F']\n")
        self.assertIn("F401", self.fb(self.write("a.py", "LINT\n")))

    def test_pyproject_without_tool_ruff_is_not_config(self) -> None:
        self.stub("ruff", RUFF_STUB)
        self.write("pyproject.toml", "[project]\nname='x'\n# see [tool.ruff] docs\n")
        self.assertEqual(self.fb(self.write("a.py", "LINT\n")), "")

    def test_config_above_repository_root_is_ignored(self) -> None:
        self.stub("ruff", RUFF_STUB)
        (self.tmp / "ruff.toml").write_text("")
        self.assertEqual(self.fb(self.write("a.py", "LINT\n")), "")

    def test_missing_ruff_is_silent(self) -> None:
        self.write("ruff.toml", "")
        self.assertEqual(self.fb(self.write("a.py", "LINT FMT\n")), "")

    def test_long_output_is_clipped(self) -> None:
        self.stub("ruff", LONG_RUFF_STUB)
        self.write("ruff.toml", "")
        out = self.fb(self.write("a.py", "x\n"))
        self.assertIn(f"... {100 - post_edit.MAX_LINES} more lines", out)
        self.assertNotIn("a.py:100:1", out)

    # -- C++ -------------------------------------------------------------

    def test_cpp_format_finding_reported_with_fix_command(self) -> None:
        self.stub("clang-format", CLANG_FORMAT_STUB)
        self.write(".clang-format", "BasedOnStyle: LLVM\n")
        path = self.write("src/a.cpp", "int  FMT;\n")
        out = self.fb(path)
        self.assertIn(f"would reformat this file in 1 place; run: clang-format -i {path}", out)
        self.assertNotIn("error:", out)

    def test_cpp_without_clang_format_config_is_silent(self) -> None:
        self.stub("clang-format", CLANG_FORMAT_STUB)
        self.assertEqual(self.fb(self.write("a.hpp", "FMT\n")), "")

    def test_cpp_unreadable_clang_format_config_is_silent(self) -> None:
        self.stub("clang-format", CLANG_FORMAT_BAD_CONFIG_STUB)
        self.write(".clang-format", "InsertNewlineAtEOF: true\n")
        self.assertEqual(self.fb(self.write("src/a.cpp", "int  FMT;\n")), "")

    def test_cpp_timeout_is_silent(self) -> None:
        self.stub("clang-format", SLEEP_STUB)
        self.write(".clang-format", "")
        old = post_edit.TIMEOUT_SECONDS
        post_edit.TIMEOUT_SECONDS = 1
        self.addCleanup(setattr, post_edit, "TIMEOUT_SECONDS", old)
        self.assertEqual(self.fb(self.write("a.cc", "FMT\n")), "")

    # -- Payload handling --------------------------------------------------

    def test_other_suffixes_and_bad_payloads_are_silent(self) -> None:
        self.assertEqual(self.fb(self.write("README.md", "LINT FMT\n")), "")
        self.assertEqual(post_edit.feedback({}, {}), "")
        self.assertEqual(post_edit.feedback({"tool_input": "x"}, {}), "")
        self.assertEqual(post_edit.feedback({"tool_input": {"file_path": 3}}, {}), "")
        self.assertEqual(self.fb(self.repo / "deleted.py"), "")

    def test_relative_path_resolves_against_payload_cwd(self) -> None:
        self.stub("ruff", RUFF_STUB)
        self.write("ruff.toml", "")
        self.write("a.py", "LINT\n")
        out = post_edit.feedback({"cwd": str(self.repo), "tool_input": {"file_path": "a.py"}}, {})
        self.assertIn("F401", out)

    def test_disable_switch(self) -> None:
        self.stub("ruff", RUFF_STUB)
        self.write("ruff.toml", "")
        self.assertEqual(self.fb(self.write("a.py", "LINT\n"), {"CLAUDE_POST_EDIT_DISABLE": "1"}), "")

    # -- As Claude Code runs it ------------------------------------------

    def run_hook(self, stdin: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True, timeout=30)

    def test_subprocess_findings_exit_2_on_stderr(self) -> None:
        self.stub("ruff", RUFF_STUB)
        self.write("ruff.toml", "")
        path = self.write("a.py", "LINT\n")
        proc = self.run_hook(json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(path)}}))
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertIn("F401", proc.stderr)

    def test_subprocess_clean_and_garbage_exit_0(self) -> None:
        self.stub("ruff", RUFF_STUB)
        self.write("ruff.toml", "")
        path = self.write("a.py", "x = 1\n")
        clean = self.run_hook(json.dumps({"tool_input": {"file_path": str(path)}}))
        self.assertEqual((clean.returncode, clean.stderr), (0, ""))
        garbage = self.run_hook("{not json")
        self.assertEqual(garbage.returncode, 0)
        self.assertIn("internal error", garbage.stderr)

    @unittest.skipUnless(shutil.which("ruff"), "ruff not installed")
    def test_real_ruff(self) -> None:
        os.environ["PATH"] = self.old_path
        self.write("ruff.toml", "[lint]\nselect = ['F']\n")
        out = self.fb(self.write("a.py", "import os\n"))
        self.assertIn("F401", out)
        self.assertEqual(self.fb(self.write("b.py", "x = 1\n")), "")


class SettingsHookTest(unittest.TestCase):
    """The exact PostToolUse command from settings.json, run through /bin/sh as Claude Code does."""

    def hook_command(self) -> str:
        entries = json.loads(SETTINGS.read_text())["hooks"]["PostToolUse"]
        self.assertEqual([e["matcher"] for e in entries], ["Write|Edit|MultiEdit"])
        return entries[0]["hooks"][0]["command"]

    def run_hook(self, home: Path, bin_dir: Path, file_path: Path) -> subprocess.CompletedProcess[str]:
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_POST_EDIT_DISABLE"}
        env.update(
            HOME=str(home), PATH=os.pathsep.join([str(bin_dir), str(Path(sys.executable).parent), "/usr/bin", "/bin"])
        )
        return subprocess.run(
            ["/bin/sh", "-c", self.hook_command()],
            input=json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(file_path)}}),
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            check=False,
        )

    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home)
        self.bin = self.home / "bin"
        self.bin.mkdir()
        (self.bin / "python3").symlink_to(sys.executable)
        ruff = self.bin / "ruff"
        ruff.write_text(RUFF_STUB)
        ruff.chmod(0o755)
        repo = self.home / "repo"
        (repo / ".git").mkdir(parents=True)
        (repo / "ruff.toml").write_text("")
        self.dirty = repo / "a.py"
        self.dirty.write_text("LINT\n")

    def test_missing_script_is_silent(self) -> None:
        proc = self.run_hook(self.home, self.bin, self.dirty)
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, "", ""))

    def test_installed_script_reports_findings(self) -> None:
        hooks = self.home / "github" / "agents" / "claude" / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "post_edit.py").symlink_to(HOOK)
        proc = self.run_hook(self.home, self.bin, self.dirty)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertIn("F401", proc.stderr)


if __name__ == "__main__":
    unittest.main()
