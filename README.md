# agents

Private personal layer for AI agents.
This repo version-controls the files that define how agents work for me but are too personal for the public [dotfiles-mac-nix](https://github.com/shreejitverma/dotfiles-mac-nix) repo.

| File | Linked to | Purpose |
|---|---|---|
| `CLAUDE.md` | `~/.claude/CLAUDE.md` | Global agent operating manual, cross-tool instructions, default development system |
| `OPINIONS.md` | `~/OPINIONS.md` | Personal engineering viewpoints agents read on demand |
| `VOICE.md` | `~/VOICE.md` | How agents speak or post on my behalf |
| `claude/settings.json` | `~/.claude/settings.json` | Claude Code settings |

`~/AGENTS.md` remains a symlink to `~/.claude/CLAUDE.md`, so the cross-tool chain (`~/.codex/AGENTS.md` and friends) resolves through this repo.

The symlinks are created by `ic-link` from dotfiles-mac-nix and verified by `ic-doctor`.
Edit the files here (or through their symlinks; writes pass through), then commit and push as usual.
