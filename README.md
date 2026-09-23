# agents

Private personal layer for AI agents.
This repo version-controls the files that define how agents work for me but are too personal for the public [dotfiles-nix](https://github.com/shreejitverma/dotfiles-nix) repo.

## One source, one manual per tool

Each AI tool reads its own operating manual, tuned for that tool.
The rules shared by every tool exist exactly once, in `CORE.md`, and are compiled into each manual, so the manuals cannot drift apart.

Edit these:

| Source | Purpose |
|---|---|
| `CORE.md` | Rules identical for every tool. The single copy that exists. |
| `ROUTING.md` | Which tool and model gets which task, and how quota decides between them. |
| `tools/claude.md` | Claude Code tuning only. Additive; never restates a `CORE.md` rule. |
| `tools/grok.md` | Grok Build tuning only. |
| `tools/gemini.md` | Gemini tuning only. |

Then run `bin/build-manuals`, which writes these:

| Generated | Linked to | Contents |
|---|---|---|
| `CLAUDE.md` | `~/.claude/CLAUDE.md` | core + routing + Claude tuning |
| `GROK.md` | `~/.grok/AGENTS.md` | core + routing + Grok tuning |
| `GEMINI.md` | `~/.gemini/AGENTS.md` | core + routing + Gemini tuning |
| `AGENTS.md` | `~/AGENTS.md` (and `~/.codex/AGENTS.md` through it) | core + routing, no tool tuning |

`AGENTS.md` is the neutral default for Codex and any other `AGENTS.md` reader.
`ic-link` points `~/AGENTS.md` at it, and `~/.codex/AGENTS.md` links to `~/AGENTS.md`, so no tool reads another tool's tuning.
`ic-doctor` fails if `~/AGENTS.md` resolves to Claude's manual while this build exists.

Never hand-edit a generated manual; `bin/build-manuals --check` fails when one is stale or edited.
`.github/workflows/ci.yml` runs that check, and shellcheck over the generator, on every pull request and every push to `main`.
Run it locally too before committing, since CI reports after the fact; `ic-doctor` runs the same check, so a drifted machine is caught outside CI as well.
`build-manuals` also refuses to build when a tuning file, a `grok/agents/` prompt, or a `claude/agents/` or `claude/rules/` file repeats a line from `CORE.md` or `ROUTING.md` byte for byte, because a second copy of a rule is how manuals drift and how one tool ends up contradicting another.
The agent prompts are covered because a Grok subagent loads the generated manual next to its prompt (`agents_md: true`), and Claude loads its subagents and rules into the same context as its manual, so either would otherwise see the same rule twice, in two strengths.
That comparison is whole-line and exact, so it is a backstop against verbatim copies and nothing more.
A reworded rule passes it: every real restatement removed from these files so far was a paraphrase, found by reading rather than by the build.
Keeping rules unduplicated in substance is therefore a review responsibility, not something a green build proves.

The manuals are generated at the repo root rather than into `build/`, because `ic-link` already points `~/.claude/CLAUDE.md` at that exact path.
The known cost is that the generated manuals double as this repo's own project instructions, so a session working here loads the shared text more than once.
Claude, Grok and Codex load it twice: once from the global manual, and again from the root `CLAUDE.md` or `AGENTS.md`, which loads as a project file on top of it.
Gemini loads it three times, because `context.fileName` lists both `GEMINI.md` and `AGENTS.md` and the repo root now holds both, on top of the global `~/.gemini/AGENTS.md` link.
Moving them would mean repointing every link `ic-link` writes, so the location stays until that cost buys something.

Other versioned files:

| File | Linked to | Purpose |
|---|---|---|
| `grok/agents/` | `~/.grok/agents/` | Grok user agent definitions (`implementer`, `reviewer`) |
| `claude/agents/` | `~/.claude/agents/` (one link per file) | Claude subagents: `cpp-reviewer`, `python-reviewer`, `silent-failure-hunter`, `pr-test-analyzer`, `type-design-analyzer`, `cpp-build-resolver` |
| `claude/rules/` | `~/.claude/rules/` (one link per file) | Path-scoped Claude rules for C++ and Python files |
| `claude/hooks/guard.py` | run from `claude/settings.json` | PreToolUse guard for destructive shell commands and check-config edits; tests in `claude/hooks/test_guard.py` |
| `claude/hooks/post_edit.py` | run from `claude/settings.json` | PostToolUse lint feedback (ruff, clang-format) using only the edited project's own config; tests in `claude/hooks/test_post_edit.py` |
| `ruff.toml` | none | Lint and format settings for the Python under `claude/hooks` |
| `OPINIONS.md` | `~/OPINIONS.md` | Personal engineering viewpoints agents read on demand |
| `VOICE.md` | `~/VOICE.md` | How agents speak or post on my behalf |
| `claude/settings.json` | `~/.claude/settings.json` | Claude Code settings |

## Per-tool wiring notes

Gemini needs two things because `~/.gemini/GEMINI.md` is Gemini's own memory file, written by `/memory add`.
It must never become a symlink into this repo, or Gemini writes into a versioned file.
Instead `~/.gemini/AGENTS.md` links to the generated manual and `~/.gemini/settings.json` lists both filenames in `context.fileName`, so rules and memories load together without either overwriting the other.

Grok owns `~/.grok/config.toml` and rewrites it on start, so it is neither linked nor versioned here.

`claude/settings.json` enables the `compact-adviser` plugin from a directory marketplace at the local clone `~/github/compact-adviser`, so that clone must exist and Claude reads the plugin's hooks live from it.
Its function-hook mod needs `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`, set in the same file's `env`; without it `/compact-adviser` does not appear.
Never save the TypeSafe API key through the `/compact-adviser` menu, because it writes `typesafeApiKey` into this tracked file; the key comes from the macOS Keychain via a dotfiles-nix shell wrapper instead.

Grok's README documents a 10,000-character cap per rules file.
Measured on Grok 1.0.34 it is not enforced: a 16,693-character manual loaded whole, which `grok inspect` confirmed at 4.00 characters per token.
That is a record of one measurement, not a running total of the generated file, which changes with every edit.
`build-manuals` therefore warns past a 20,000-character ceiling set above the current manual rather than at the documented cap, so steady state is silent and only unbounded growth is flagged.
Re-measure with `grok inspect` after a Grok upgrade before assuming a long manual still loads.

`ic-link` from dotfiles-nix creates every link in the tables above: the `~/AGENTS.md` and `~/.codex/AGENTS.md` chain, the Claude manual, settings, subagents, and rules, `~/OPINIONS.md`, `~/VOICE.md`, the skill mirrors, and, when their installers have created `~/.grok` and `~/.gemini`, Grok's manual and agent definitions and Gemini's manual.
`ic-doctor` verifies the same set, every hook script `claude/settings.json` runs, and `bin/build-manuals --check`.
Run `grok` and `gemini` once first so each installer creates its own top-level directory; `ic-link` never creates either.

Links are all `ic-link` recreates.
`tools/grok.md` also asserts that Claude and Cursor compatibility is off and that Grok runs `grok-4.7` at high effort, all of which lives in `~/.grok/config.toml`.
Because that file is unversioned here, apply these keys by hand after running `grok` once to reach the state the manual describes.

```toml
[models]
default = "grok-4.7"
default_reasoning_effort = "high"

[ui]
fork_secondary_model = "grok-4.7"

[compat.claude]
skills = false
rules = false
agents = false
mcps = false
hooks = false

[compat.cursor]
skills = false
rules = false
agents = false
mcps = false
hooks = false
```

These key names are read from the working config on this Mac rather than from Grok's published documentation, and cover only the model and compatibility settings `tools/grok.md` asserts.
Treat them as the intended setting and confirm the result with `grok inspect`.

`ic-link` mirrors every IC skill into `~/.grok/skills` as well as `~/.claude/skills`, which is one of the four directories Grok discovers skills from, so `grok inspect` lists some skills twice, including `axi` and `no-mistakes`.
That duplication is expected and harmless; the skill set itself is defined in dotfiles-nix, not here.

Gemini also needs `context.fileName` in `~/.gemini/settings.json` set to `["GEMINI.md", "AGENTS.md"]`, or the linked manual is never loaded.

Edit the sources here, run `bin/build-manuals`, then commit and ship through the `no-mistakes` pipeline; never push bare.
