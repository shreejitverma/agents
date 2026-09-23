## Default development system
firstmate is the default for all AI work: every request to build, fix, investigate, plan, or audit a project runs through the first mate, which dispatches and supervises crewmates in isolated worktrees and ships through the toolchain below.
- Start every AI work session from the firstmate workspace with `fm` (Claude Code as the first mate; `fm <harness>` for another verified primary), then talk to the first mate: register the project there once and delegate the work.
- Already running as the first mate (the firstmate `AGENTS.md` contract is loaded) or as a crewmate it launched: you are inside the system, so follow that contract or your brief and never launch another firstmate.
- In a plain session outside firstmate, say once that firstmate is the default and give the `fm` command; if the user continues directly, treat that as their decision and follow the `ship` skill.
The integrated IC toolchain below is what firstmate and its crew use, and it remains the default for direct development requests in every AI tool.
Prefer these tools over ad hoc equivalents whenever they apply; the `ship` skill encodes the full loop for any direct request to build, fix, or ship.
- `firstmate`: the agent-of-agents workspace at `~/github/firstmate`; the default supervisor for all AI work, entered with `fm`.
- AI tool choice: route every task in two steps, by fit first and by quota second, across Claude Code Max, Grok Build, and Gemini Pro (run through `agy`, the only surface `quota-axi` can measure Gemini on).
  Step 1, classify the task and take the best model for that class.
  Tier 1, frontier reasoning (architecture, risky or wide refactors, concurrency and lifetime work, root-cause debugging, security-sensitive or measured performance work, ambiguous multi-file tasks): Claude Fable at high effort, and nothing else while Claude has runway; Fable's separate weekly window is spent only here.
  Tier 2, standard well-specified coding (scoped features, known-cause fixes, tests, contained refactors, normal reviews): Claude Opus 5.5 at 1M context (`claude-opus-5-5[1m]`) and Grok 4.7 (`grok-4.7`), both at high effort, and Gemini 3.1 Pro.
  Opus is the strongest of the three rather than a true peer, so a quota win for Grok or Gemini here trades some quality for subscription utilization, which is sound only because the spec is already clear and `no-mistakes` gates the result.
  Tier 3, mechanical work (renames, lint and format sweeps, typo fixes, bumps, boilerplate): Claude Haiku, Grok 4.5, and Gemini Flash are peers.
  Live or post-cutoff information and X research go to Grok first, then Gemini.
  Multimodal evidence, one-pass ingestion of a very large corpus, and investigations of Google's own platforms go to Gemini first, then Claude Opus 5.5 at 1M context.
  Step 2, read `quota-axi` and pick within the class: drop any candidate whose runway is `exhausted_now` or projected to exhaust before the task would finish, then among the surviving peers take the highest `spendPriority`, so the subscription with the most use-it-or-lose-it headroom before its reset gets the work.
  Unknown runway or `spendPriority` keeps a candidate eligible but never ranks it above a peer with known viable evidence.
  Tier 1 never balances by `spendPriority`: when Claude cannot carry it, fall back in order to Claude Opus 5.5 at 1M context (it draws on the shared window, so it survives a spent Fable week), Grok 4.7, then Gemini 3.1 Pro, and if none has runway stop and report rather than downgrade.
  Before any long run, size it against the limiting window, not the headline percentage: Claude Max has a five-hour session window inside the weekly one, a 1M-context session drains it far faster than a small one, and a single long gate run can drain a whole week of Grok credits.
  Re-read `quota-axi` when a task is handed over mid-flight, and restore any tool setting changed for a fallback once the preferred tool has runway again.
  Pick by these rules, never by habit; inside firstmate `config/crew-dispatch.json` encodes the same rules and `quota-array-dispatch` resolves each peer array.
- `quota-axi`: check subscription headroom before starting long or expensive agent runs.
- `tasks-axi`: track multi-step work in the workspace backlog; record the PR when completing a task.
- `treehouse`: one git worktree per independent stream of work; never juggle streams in one checkout.
- `gh-axi`: GitHub operations (issues, PRs, CI runs, releases) in agent-ergonomic form.
- `chrome-devtools-axi`: real-browser verification for anything with a web surface.
- `lavish-axi`: render plans, reviews, and comparisons as rich artifacts when visual beats prose.
- `no-mistakes`: the ship gate and the only way to ship; every change reaches the remote through it (review, tests, lint, docs, push, PR, CI), never via bare `git push`.
- `stow` skill: sweep durable knowledge to disk before ending a long session.
- `ic-doctor`: run when the toolchain itself misbehaves; each FAIL line names its fix.
Toolchain setup and integration details live in `~/github/dotfiles-nix/README.md`.
How these per-tool manuals are built, and which file to edit to change a rule, lives in `~/github/agents/README.md`.
