## Gemini on this Mac

### Where repo-local rules belong
- Put repo-specific build commands, test commands, architecture notes, and naming rules in the project's `GEMINI.md` or `AGENTS.md`.
- Put Gemini-only global additions that are not this operating manual in `~/.gemini/` alongside the linked manual, never inside it.

Gemini reaches work through two different surfaces, and the difference matters.
- `gemini` is the Gemini CLI, used directly for interactive and headless work.
- `agy` is the Antigravity CLI. Firstmate dispatches Gemini through `agy` because that is the only Gemini surface `quota-axi` can measure, and because the bare `gemini` harness is rejected by dispatch validation unless typed resolution is enabled.

### Rules and memory are separate files, deliberately
`~/.gemini/GEMINI.md` is Gemini's own memory file: `/memory add` and the "Gemini Added Memories" section are written by Gemini itself.
It must never be a symlink into `~/github/agents`, or Gemini writes into a versioned repo the way Grok rewrites its own `config.toml`.
This manual is therefore linked at `~/.gemini/AGENTS.md`, and `~/.gemini/settings.json` lists both filenames in `context.fileName` so rules and memories load together without either overwriting the other.

### Models
- `gemini-3.1-pro-high` is the reasoning model; use it for Tier 1 fallback, Tier 2 work, and every task where Gemini is the first choice.
- `gemini-3.1-pro-low` trades depth for speed on well-specified work.
- `gemini-3.8-flash-medium` and the other Flash tiers are for mechanical Tier 3 work only.
Run `agy models` for the live catalog; `fm-spawn` validates the model against that listing before launch and refuses an unlisted id.

### What Gemini is genuinely best at
Take these ahead of Claude and Grok rather than as a fallback.
- Multimodal evidence the worker must actually look at or listen to: images, screenshots, video, audio, scanned PDFs.
- One-pass ingestion of a very large corpus for a knowledge deliverable, such as a document set, a transcript corpus, or an entire codebase read for a summary or audit rather than a change.
- Investigations centered on Google's own platforms: Gemini API, Vertex AI, Google Cloud, Firebase, Workspace, Android.

### Quota shape
`quota-axi` reports Gemini under the `agy` provider with a five-hour and a weekly window.
Both currently report `spendPriority: unknown`, so Gemini can never win a quota-balanced array on rank; it is selected when it is the best fit for the class, or when every other candidate fails the runway floor.
Treat unknown as eligible with disclosed uncertainty, never as a reason to skip it.

### Wiring
Gemini has no part in the `no-mistakes` pipeline by default.
When Claude and Grok are both exhausted, the gate can run Gemini only as `agent: acp:gemini`, which requires `acpx` to be installed; plain `agent: gemini` is not a supported value.
Restore `agent: auto` once Claude has runway again.
