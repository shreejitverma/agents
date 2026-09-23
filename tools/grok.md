## Grok on this Mac

### Where repo-local rules belong
- Put repo-specific build commands, test commands, architecture notes, and naming rules in the project's `AGENTS.md`.
- Put path-specific or language-specific repo rules in `.grok/rules/`.
- Put Grok agent definitions in `~/github/agents/grok/agents/`.
- Put Grok-only global additions that are not this operating manual in `~/.grok/rules/`.

Grok Build is installed as the native aarch64 binary (`~/.local/bin/grok`).
That is the only copy on PATH.
Do not install `@xai-official/grok` via npm; a second copy on PATH shadows the native binary.
The symlinks below are created by hand today: the installed `ic-link` and `ic-doctor` carry no Grok wiring yet, which is a pending follow-up blocked on dotfiles-nix PR 14.
Firstmate already treats `grok` as a verified harness.

| Path | Purpose |
|---|---|
| `~/github/agents/GROK.md` | This operating manual; linked to `~/.grok/AGENTS.md` |
| `~/github/agents/grok/agents/` | User agent definitions; linked into `~/.grok/agents/` |
| `~/.grok/skills/` | IC skill mirrors, same set as Claude and Codex |
| `~/.grok/hooks/` | Firstmate-owned turn-end hooks; never replace this directory |
| `~/.grok/rules/` | Optional Grok-only global rules, not this manual |

Compatibility with Claude and Cursor named instruction files, MCP servers, and hooks is off.
Project `AGENTS.md` files still load natively.

Grok's own README documents exactly four skill-discovery directories, and these are the only ones in use here: `./.grok/skills/`, `<repo_root>/.grok/skills/`, `~/.grok/skills/` and `~/.claude/skills/`.
`~/.agents/skills` is not one of them; it is the canonical store, reached only through the mirror symlinks pointing into it.
Extra directories would need a `[skills] paths` key in `~/.grok/config.toml`, and there is no `[skills]` section there.
`ic-link` populates `~/.claude/skills` with the IC set, so those skills reach Grok through that directory even when `~/.grok/skills` is absent.
The same set is mirrored into `~/.grok/skills` here, and `grok inspect` lists some skills twice, including `axi` and `no-mistakes`.

Firstmate:
- Primary: `fm grok` launches Grok as the first mate in the firstmate workspace.
- Crewmate: firstmate already dispatches `grok --always-approve` with `--model` / `--reasoning-effort` when the coding rule selects Grok as the Claude quota fallback.
- Do not create `~/.grok`; the Grok installer owns that directory.
- Do not install or overwrite files under `~/.grok/hooks/`; firstmate's spawn path owns the global turn-end hook.

no-mistakes:
- The pipeline agent is Claude by default (`agent: auto`). Switch `~/.no-mistakes/config.yaml` to `agent: grok` only while Claude has no runway; `agent_path_override.grok` already pins `~/.local/bin/grok`.
- no-mistakes already launches Grok with Claude and Cursor compatibility environment variables forced off, plus `GROK_MEMORY=0`.
- The pipeline agent still loads this file.
- Restore `agent: auto` as soon as Claude has runway again.

Verify with `grok inspect`: this file must appear as a loaded instruction.

Grok owns `~/.grok/config.toml` and rewrites it on start, so `ic-link` deliberately does not link it and this repo does not version a copy of it.
Its `[models]` table pins `default = "grok-4.7"` and `default_reasoning_effort = "high"`, with `fork_secondary_model = "grok-4.7"` under `[ui]`.
The same model and effort are pinned for the gate in `~/.no-mistakes/config.yaml` (`agent_config.grok`) and for crewmates in firstmate's `config/crew-dispatch.json`; bump all three together on a Grok release.

Measured on 1.0.34: the 10,000-character per-file cap in Grok's own README is not enforced.
A 16,693-character manual loaded whole, which `grok inspect` confirmed by reporting it at 4.00 characters per token.
That figure records one measurement, not the current size of this file, which moves with every edit; the build's 20,000-character ceiling is what watches for growth.
Re-measure with `grok inspect` after a Grok upgrade before assuming a long manual still loads.
