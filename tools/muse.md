## Muse Code on this Mac

### Where rules load from
- This manual is linked at `~/.config/muse/AGENTS.md`, Muse's native personal rules file (`$XDG_CONFIG_HOME/muse/AGENTS.md`).
- A native file replaces Muse's fallback of loading `~/.claude/CLAUDE.md`, so Muse never reads Claude's tuning as its own.
- Firstmate launches Muse crewmates with `MUSE_EXPERIMENTAL_FOREIGN_PERSONAL_CONTEXT_KILL=on`, which drops only foreign rules; this native manual still reaches every crewmate.
- Muse sends loaded rules to Meta-hosted inference on every run, so keep secrets, credentials, and private notes out of every source this manual is built from.
- Put repo-specific rules in the project's `AGENTS.md`, which Muse also loads.
- Run `/rules` inside a session to see exactly which files govern it.

### Skills
Muse discovers `~/.agents/skills` directly as user skills, so every directory there loads, including hidden backup copies; keep backups outside that tree.
`muse skills list` shows what loaded and from where.

### Autonomy and git
Approval and the OS sandbox are on by default; `--yolo` disables both for one run, which is how Firstmate launches crewmates.
Muse's bundled `git` skill never commits, pushes, tags, rebases, or hard-resets unless asked for that exact write in the same session, which matches shipping only through `no-mistakes`.

### Headless use
`muse exec` runs one prompt non-interactively; `--json` streams JSONL events, `--output-schema <file>` shapes the final answer, and `--max-model-steps <n>` bounds the run.
`--reasoning-effort` accepts `none|minimal|low|medium|high|xhigh|max|ultra` and defaults to `high`.

### Credentials, quota, and routing status
- `muse login` or `muse auth set --api-key-stdin` stores the credential in `~/.config/muse/auth.json`; `META_API_KEY` overrides it.
- `quota-axi` reports Muse under the `muse` provider and may need one `quota-axi --allow-keychain-prompt` run before it can read the credential.
- An HTTP 402 `billing_error` means the Meta team behind the key must resolve billing at `dev.meta.ai`; it is not a login problem.
- Muse is not yet a routing peer: it joins Tier 2 and Tier 3 only after a credentialed run succeeds and `quota-axi` measures its runway.
- Muse has no role in the `no-mistakes` pipeline and is not a supported `agent:` value there.

### Auto-update
The launcher at `~/.local/bin/muse` silently replaces the `muse-bin-<version>` binary it runs.
After any upgrade, rerun Firstmate's Muse live guards before trusting earlier verification; `docs/verification/muse.md` in firstmate names them.
