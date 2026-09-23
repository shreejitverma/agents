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
  Opus 5.5 ships defaulting to `medium`, and a top-level `effortLevel` in the user settings file (`~/.claude/settings.json`, this repo's `claude/settings.json`) does not apply to it, so that file sets its default to `high` through `modelSettings.claude-opus-5-5.effortLevel`, which takes precedence over any top-level key; `/effort` with Enter overwrites that entry.

### Skills and wiring
IC skills load from `~/.claude/skills`, mirrored from `~/.agents/skills` by `ic-link`.
This manual is generated; `~/.claude/CLAUDE.md` is a link to the generated build and must never be hand-edited.

### Subagents, rules, and hooks
These live in this repo under `claude/` and `ic-link` links them into `~/.claude`.
- Subagents give a fresh-context second opinion before the gate: `cpp-reviewer` and `python-reviewer` for a nontrivial C++ or Python diff, `silent-failure-hunter` for code that moves data, money, orders, or state, `pr-test-analyzer` for whether the tests prove the change, `type-design-analyzer` for new domain types, and `cpp-build-resolver` for a failing C++ build.
  All but `cpp-build-resolver` are read-only; their findings feed the `no-mistakes` gate and never replace it.
  Each preloads its skills and pins `claude-opus-5-5` at high effort, so delegated review never spends Fable's window; bump that pin together with `claude/settings.json`.
- `claude/rules/cpp.md` and `claude/rules/python.md` load only when matching files are read, and carry the build, test, and toolchain commands for those languages.
- `claude/hooks/guard.py` runs before every Bash and edit call.
  It always denies skipping git hooks (`--no-verify`, a `core.hooksPath` override), force-pushing or deleting a shared branch, and recursive removal of a critical path.
  It asks before other destructive commands (`reset --hard`, `clean -f`, `rm -rf` outside build artifacts and temp directories, `branch -D`, destructive SQL) and before editing an existing lint, format, or gate config, but only when a human is present; unattended runs (`claude -p`, firstmate crewmates) are allowed the destructive commands and denied the config edits.
  When the guard refuses something that is genuinely intended, ask the user to run it with the `!` prefix; never work around it with another command.
- `claude/hooks/post_edit.py` runs after every edit and reports the file's problems back to you: `ruff check` and `ruff format --check` for Python when the project configures ruff, `clang-format --dry-run` for C and C++ when it has a `.clang-format`.
  It runs only what the project itself configures, stays silent on a clean file, and never blocks; fix what it reports before moving on rather than leaving it for the `no-mistakes` gate.
