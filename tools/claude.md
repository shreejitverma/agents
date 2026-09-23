## Claude Code on this Mac

Claude Code is the default first mate and the default `no-mistakes` pipeline agent.
`fm` launches it as the primary; `no-mistakes` uses it as the pipeline agent whenever `~/.no-mistakes/config.yaml` is set to `agent: auto`.

### Where repo-local rules belong
- Put repo-specific build commands, test commands, architecture notes, and naming rules in the project's `CLAUDE.md`.
- Put path-specific or language-specific repo rules in `.claude/rules/`.
- Put personal per-repo exceptions in `CLAUDE.local.md`.

### Model and effort
Claude is the only tool here with more than one reasoning class, so pick deliberately rather than taking the session default.
- `fable` is the strongest model and has its own weekly window, separate from every other Claude model.
  Spend it only on Tier 1 frontier work, because exhausting it does not touch the shared window but cannot be refilled early.
- `claude-opus-5-5[1m]` (Opus 5.5) is the workhorse at 1M context and draws on the shared `all_models` window, so it still has runway after a spent Fable week.
  It is pinned by full ID rather than the `opus[1m]` alias, which moves to each new Opus release unannounced; bump the pin deliberately in `claude/settings.json` and firstmate's `config/crew-dispatch.json` together.
- `haiku` is for mechanical work only.
- Effort runs `low`, `medium`, `high`, `xhigh`, `max`.
  Use `high` as the floor for anything intelligence-sensitive and `xhigh` for long-horizon agentic work; reserve `max` for correctness-over-cost cases.
  Opus 5.5 ships defaulting to `medium` and ignores the legacy top-level `effortLevel`, so `claude/settings.json` sets its default to `high` through `modelSettings`; `/effort` with Enter overwrites that entry.

### Skills and wiring
IC skills load from `~/.claude/skills`, mirrored from `~/.agents/skills` by `ic-link`.
This manual is generated; `~/.claude/CLAUDE.md` is a link to the generated build and must never be hand-edited.
