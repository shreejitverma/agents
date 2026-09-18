## Grok on this Mac

### Where repo-local rules belong
- Put repo-specific build commands, test commands, architecture notes, and naming rules in the project's `AGENTS.md`.
- Put path-specific or language-specific repo rules in `.grok/rules/`.
- Put Grok agent definitions in `~/github/agents/grok/agents/`.
- Put Grok-only global additions that are not this operating manual in `~/.grok/rules/`.

Grok Build is installed as the native aarch64 binary (`~/.local/bin/grok`).
That is the only copy on PATH.
Do not install `@xai-official/grok` via npm; `ic-doctor` and fleet-ops doctor fail on a second copy.
`ic-link` wires the personal layer; `ic-doctor` verifies it; firstmate already treats `grok` as a verified harness.

| Path | Purpose |
|---|---|
| `~/github/agents/GROK.md` | This operating manual; linked to `~/.grok/AGENTS.md` |
| `~/github/agents/grok/agents/` | User agent definitions; linked into `~/.grok/agents/` |
| `~/.grok/skills/` | IC skill mirrors, same set as Claude and Codex |
| `~/.grok/hooks/` | Firstmate-owned turn-end hooks; never replace this directory |
| `~/.grok/rules/` | Optional Grok-only global rules, not this manual |

Compatibility with Claude and Cursor named instruction files, MCP servers, and hooks is off.
Grok must not inherit `~/.claude/CLAUDE.md`, `~/.claude.json` MCP servers, or Claude permission allowlists.
IC skills load from `~/.grok/skills` and `~/.agents/skills`.
Project `AGENTS.md` files still load natively.

Firstmate:
- Primary: `fm grok` launches Grok as the first mate in the firstmate workspace.
- Crewmate: firstmate already dispatches `grok --always-approve` with `--model` / `--reasoning-effort` when the coding rule selects Grok as the Claude quota fallback.
- Do not create `~/.grok`; the Grok installer owns that directory.
- Do not install or overwrite files under `~/.grok/hooks/`; firstmate's spawn path owns the global turn-end hook.

no-mistakes:
- The pipeline agent is Claude by default (`agent: auto`). Switch `~/.no-mistakes/config.yaml` to `agent: grok` only while Claude has no runway; `agent_path_override.grok` already pins `~/.local/bin/grok`.
- no-mistakes already launches Grok with Claude and Cursor compatibility environment variables forced off, plus `GROK_MEMORY=0`.
- The pipeline agent still loads this file. It must not inherit `~/.claude/CLAUDE.md`, Claude MCP servers, or Claude permission allowlists.
- Restore `agent: auto` as soon as Claude has runway again.

Verify with `grok inspect` (this file must appear as a loaded instruction) and `ic-doctor`.

Grok owns `~/.grok/config.toml` and rewrites it on start, so `ic-link` deliberately does not link it.
`~/github/agents/grok/config.toml` is a reference copy only, not enforced on the machine.

Measured on 1.0.34: the 10,000-character per-file cap in Grok's own README is not enforced.
A 16,458-character manual loads whole, which `grok inspect` confirms by reporting it at 4.00 characters per token.
Re-measure with `grok inspect` after a Grok upgrade before assuming a long manual still loads.
