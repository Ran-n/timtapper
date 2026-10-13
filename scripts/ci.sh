#!/usr/bin/env bash
# ------------------------------------------------------------------------------
#+ Authors: 	Ran# <ran.hash@proton.me>
#+ Created: 	2026/10/12 22:05:36.325845
#+ Revised: 	2026/10/12 22:05:57.829463
# ------------------------------------------------------------------------------

# The checks every CI (GitHub, GitLab, Codeberg) runs, and the same ones to run locally before pushing:
# locked install, format, lint, then the default test run with the coverage gate from pyproject.toml.
set -euo pipefail

uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run pytest --cov
