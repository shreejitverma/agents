# agents

Private personal layer for AI agents.
This repo version-controls the files that define how agents work for me but are too personal for the public [dotfiles-nix](https://github.com/shreejitverma/dotfiles-nix) repo.

| File | Linked to | Purpose |
|---|---|---|
| `CLAUDE.md` | `~/.claude/CLAUDE.md` | Claude Code operating manual, and the cross-tool default at `~/AGENTS.md` |
| `GROK.md` | `~/.grok/AGENTS.md` | Grok Build operating manual (separate from Claude) |
| `grok/config.toml` | `~/.grok/config.toml` | Grok user config, compatibility flags, and model defaults |
| `grok/agents/` | `~/.grok/agents/` | Grok user agent definitions (`implementer`, `reviewer`) |
| `OPINIONS.md` | `~/OPINIONS.md` | Personal engineering viewpoints agents read on demand |
| `VOICE.md` | `~/VOICE.md` | How agents speak or post on my behalf |
| `claude/settings.json` | `~/.claude/settings.json` | Claude Code settings |

`~/AGENTS.md` remains a symlink to `~/.claude/CLAUDE.md`, so Codex and other AGENTS.md readers resolve through Claude's file.
Grok does not share that file: `ic-link` points `~/.grok/AGENTS.md` at `GROK.md`.

The shared operating rules in `CLAUDE.md` and `GROK.md` should stay in lockstep.
Grok-only wiring (config, agent definitions, compatibility flags, Mac install paths) stays in `GROK.md` and `grok/`.

The symlinks are created by `ic-link` from dotfiles-nix and verified by `ic-doctor`.
Edit the files here (or through their symlinks; writes pass through), then commit and ship through the `no-mistakes` pipeline; never push bare.
