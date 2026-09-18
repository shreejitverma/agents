# agents

Private personal layer for AI agents.
This repo version-controls the files that define how agents work for me but are too personal for the public [dotfiles-nix](https://github.com/shreejitverma/dotfiles-nix) repo.

## One source, one manual per tool

Each AI tool reads its own operating manual, tuned for that tool.
The rules shared by every tool exist exactly once, in `CORE.md`, and are compiled into each manual, so the manuals cannot drift apart and no tool ever loads another tool's file.

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
| `AGENTS.md` | neutral default for Codex and other `AGENTS.md` readers | core + routing, no tool tuning |

Never hand-edit a generated manual; `bin/build-manuals --check` fails when one is stale or edited, and that check is what keeps the three tools honest.
`build-manuals` also refuses to build when a tuning file restates a line from `CORE.md`, because a second copy of a rule is how manuals drift and how one tool ends up contradicting another.

Other versioned files:

| File | Linked to | Purpose |
|---|---|---|
| `grok/agents/` | `~/.grok/agents/` | Grok user agent definitions (`implementer`, `reviewer`) |
| `grok/config.toml` | reference copy only | Grok rewrites `~/.grok/config.toml` on start, so `ic-link` deliberately does not link it |
| `OPINIONS.md` | `~/OPINIONS.md` | Personal engineering viewpoints agents read on demand |
| `VOICE.md` | `~/VOICE.md` | How agents speak or post on my behalf |
| `claude/settings.json` | `~/.claude/settings.json` | Claude Code settings |

## Per-tool wiring notes

Gemini needs two things because `~/.gemini/GEMINI.md` is Gemini's own memory file, written by `/memory add`.
It must never become a symlink into this repo, or Gemini writes into a versioned file.
Instead `~/.gemini/AGENTS.md` links to the generated manual and `~/.gemini/settings.json` lists both filenames in `context.fileName`, so rules and memories load together without either overwriting the other.

Grok's README documents a 10,000-character cap per rules file.
Measured on Grok 1.0.34 it is not enforced: a 16,693-character manual loads whole, which `grok inspect` confirms at 4.00 characters per token.
`build-manuals` warns past 10,000 rather than failing, so a future Grok that does enforce it is noticed.
Re-measure with `grok inspect` after a Grok upgrade.

The symlinks are created by `ic-link` from dotfiles-nix and verified by `ic-doctor`.
Edit the sources here, run `bin/build-manuals`, then commit and ship through the `no-mistakes` pipeline; never push bare.
