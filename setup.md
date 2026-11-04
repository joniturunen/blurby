# Setup.md
Notes about running the dev env.

## Dependencies

Dependencies are managed with [uv](https://docs.astral.sh/uv/) and locked in `uv.lock`.

```bash
uv sync    # creates .venv with the locked runtime and dev dependencies
```

Run commands inside the environment with `uv run`, e.g. `uv run pytest`. `uv sync` installs the `blurby` package (from `src/blurby/`) in editable mode, so code changes take effect without reinstalling.

To add or upgrade a dependency use `uv add <package>` or `uv lock --upgrade-package <package>`, and commit `pyproject.toml` and `uv.lock` together. CI and the Docker image install with `uv sync --locked`, so they fail if the lockfile is out of date.

## Setting up sqlite

Run `uv run python -m blurby.setup_database`.

Note: Path to blurby's data folder must exists and be writable. By default (if not given as env) is `/blurby/data/sqlite.db`.
