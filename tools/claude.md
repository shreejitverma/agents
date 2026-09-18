## Claude Code on this Mac

Claude Code is the default AI tool and the default first mate.
`fm` launches it as the primary; `no-mistakes` uses it as the pipeline agent whenever `~/.no-mistakes/config.yaml` is set to `agent: auto`.

### Where repo-local rules belong
- Put repo-specific build commands, test commands, architecture notes, and naming rules in the project's `CLAUDE.md`.
- Put path-specific or language-specific repo rules in `.claude/rules/`.
- Put personal per-repo exceptions in `CLAUDE.local.md`.

### Model and effort
Claude is the only tool here with more than one reasoning class, so pick deliberately rather than taking the session default.
- `fable` is the strongest model and has its own weekly window, separate from every other Claude model.
  Spend it only on Tier 1 frontier work, because exhausting it does not touch the shared window but cannot be refilled early.
- `opus[1m]` is the workhorse at 1M context and draws on the shared `all_models` window, so it still has runway after a spent Fable week.
- `haiku` is for mechanical work only.
- Effort runs `low`, `medium`, `high`, `xhigh`, `max`.
  Use `high` as the floor for anything intelligence-sensitive and `xhigh` for long-horizon agentic work; reserve `max` for correctness-over-cost cases.

### Quota shape
Claude Max has a five-hour session window nested inside a seven-day one, so the headline weekly percentage can look healthy while the session window is minutes from empty.
Read the limiting window from `quota-axi`, never the top-line number.
A 1M-context session drains the shared window far faster than a small one; size long runs against that before starting.

### Skills and wiring
IC skills load from `~/.claude/skills`, mirrored from `~/.agents/skills` by `ic-link`.
This manual is generated; `~/.claude/CLAUDE.md` is a link to the generated build and must never be hand-edited.
