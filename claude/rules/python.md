---
paths:
  - "**/*.{py,pyi}"
  - "**/pyproject.toml"
  - "**/*.ipynb"
---

# Python files

- Load the `python-testing` skill before writing or fixing tests, and `mle-workflow` for models, signals, features, or backtests.
- Use the repo's environment manager (`uv run`, `poetry run`, or the checked-in virtualenv); never install into the system interpreter.
- Before calling Python work done: `ruff check` and `ruff format --check` with the repo's config, the type checker the repo configures (`mypy` or `pyright`), and `pytest` on the affected tests with warnings as errors if the repo sets `filterwarnings = ["error"]`.
- For pandas, numpy, and polars code, assert shapes, dtypes, index alignment, and NaN handling at stage boundaries; the `silent-failure-hunt` skill lists the usual ways data code fails without raising.
- Delegate a fresh-context review to the `python-reviewer` subagent.
