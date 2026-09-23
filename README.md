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
| `AGENTS.md` | no global symlink yet, see below | core + routing, no tool tuning |

`AGENTS.md` is generated as the neutral default for Codex and other `AGENTS.md` readers, but no global symlink points at it yet.
`~/AGENTS.md`, and `~/.codex/AGENTS.md` which links to it, both still resolve to `~/.claude/CLAUDE.md`, so Codex reads Claude's manual today, including its Claude-only section.
This tool-neutral `AGENTS.md` exists to replace that chain.
Repointing it is a pending follow-up: `ic-link` must retarget `~/AGENTS.md` and `ic-doctor` must stop failing on the new target, both blocked on dotfiles-nix PR 14.
PR 14 must also correct `~/github/dotfiles-nix/README.md`, which still documents the single-manual model this repo retires.
It claims that `~/.claude/CLAUDE.md` is the single source of truth for agent instructions, and concludes that Claude Code, Codex and anything else reading `AGENTS.md` all see one set of rules.
Neither holds now: `CORE.md` is the only copy of the shared rules, and every tool reads its own manual compiled from it.
Its clone step also still calls `CLAUDE.md` the agent operating manual, where `CLAUDE.md` is now a generated artifact.
Those corrections belong in that repo, next to the `ic-link` and `ic-doctor` changes PR 14 already makes, not here.

Never hand-edit a generated manual; `bin/build-manuals --check` fails when one is stale or edited.
`.github/workflows/ci.yml` runs that check, and shellcheck over the generator, on every pull request and every push to `main`.
Run it locally too before committing, since CI reports after the fact; wiring it into `ic-doctor` so a drifted machine is caught outside CI is part of the pending dotfiles-nix follow-up.
`build-manuals` also refuses to build when a tuning file or a `grok/agents/` prompt repeats a line from `CORE.md` or `ROUTING.md` byte for byte, because a second copy of a rule is how manuals drift and how one tool ends up contradicting another.
The agent prompts are covered because they set `agents_md: true`, so a Grok subagent loads the generated manual next to the prompt and would otherwise see the same rule twice, in two strengths.
That comparison is whole-line and exact, so it is a backstop against verbatim copies and nothing more.
A reworded rule passes it: every real restatement removed from these files so far was a paraphrase, found by reading rather than by the build.
Keeping rules unduplicated in substance is therefore a review responsibility, not something a green build proves.

The manuals are generated at the repo root rather than into `build/`, because `ic-link` already points `~/.claude/CLAUDE.md` at that exact path.
The known cost is that the generated manuals double as this repo's own project instructions, so a session working here loads the shared text more than once.
Claude, Grok and Codex load it twice: once from the global manual, and again from the root `CLAUDE.md` or `AGENTS.md`, which loads as a project file on top of it.
Gemini loads it three times, because `context.fileName` lists both `GEMINI.md` and `AGENTS.md` and the repo root now holds both, on top of the global `~/.gemini/AGENTS.md` link.
Revisit the output location once `ic-link` is updated.

Other versioned files:

| File | Linked to | Purpose |
|---|---|---|
| `grok/agents/` | `~/.grok/agents/` | Grok user agent definitions (`implementer`, `reviewer`) |
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

`ic-link` from dotfiles-nix wires only the Claude side: the `~/AGENTS.md` and `~/.codex/AGENTS.md` chain, `~/.claude/CLAUDE.md`, `~/.claude/settings.json`, `~/OPINIONS.md`, `~/VOICE.md` and the skill mirrors.
`ic-doctor` verifies that same set and nothing else.
The Grok and Gemini links below were made by hand and no tool recreates them; Grok wiring is incoming with dotfiles-nix PR 14, and Gemini wiring does not exist anywhere yet.
Until then, recreate them by hand on a fresh machine.
Run `grok` and `gemini` once first so each installer creates its own top-level directory; only the subdirectories below are safe to create by hand.

```sh
if [ -d ~/.grok ] && [ -d ~/.gemini ]; then
  mkdir -p ~/.grok/agents
  ln -sfn ~/github/agents/GROK.md                     ~/.grok/AGENTS.md
  ln -sfn ~/github/agents/grok/agents/implementer.md  ~/.grok/agents/implementer.md
  ln -sfn ~/github/agents/grok/agents/reviewer.md     ~/.grok/agents/reviewer.md
  ln -sfn ~/github/agents/GEMINI.md                   ~/.gemini/AGENTS.md
else
  echo "run grok and gemini once each first; their installers own ~/.grok and ~/.gemini"
fi
```

Symlinks are all that block recreates.
`tools/grok.md` also asserts that Claude and Cursor compatibility is off and that Grok runs `grok-4.7` at high effort, all of which lives in `~/.grok/config.toml`.
Because that file is unversioned here, apply these keys by hand after running `grok` once to reach the state the manual describes.

```toml
[models]
default = "grok-4.7"
default_reasoning_effort = "high"

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

Mirroring the IC skills into Grok's own directory is optional:

```sh
if [ -d ~/.grok ]; then
  mkdir -p ~/.grok/skills
  for s in axi chrome-devtools-axi gh-axi gnhf lavish no-mistakes quota-axi ship stow tasks-axi; do
    ln -sfn "../../.agents/skills/$s" "$HOME/.grok/skills/$s"
  done
fi
```

`ic-link` populates `~/.claude/skills`, which is one of the four directories Grok discovers skills from, so the IC skills already reach Grok without this mirror.
Its effect is to make the same skills resolve from `~/.grok/skills` as well, and `grok inspect` lists some skills twice, including `axi` and `no-mistakes`.
If you run it, keep the list in step with `ALL_SKILLS` in `ic-link`.

Gemini also needs `context.fileName` in `~/.gemini/settings.json` set to `["GEMINI.md", "AGENTS.md"]`, or the linked manual is never loaded.

Edit the sources here, run `bin/build-manuals`, then commit and ship through the `no-mistakes` pipeline; never push bare.
