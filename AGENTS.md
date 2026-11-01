# Agent instructions

## Project

This Home Assistant integration connects to bank accounts through FinTS/HBCI and exposes account balances as sensors.

## Working in this repository

- Read `README.md` before changing bank setup, authentication recovery, or account handling.
- Keep bank credentials in Home Assistant's config-entry flow and out of source, logs, and fixtures.
- Before changing CI, check [pschmitt/ci-workflows](https://github.com/pschmitt/ci-workflows) for reusable components and preserve this repository's existing checks.

## Validation

- Run `python3 scripts/hassfest.py` for the Hassfest check and `uvx ruff check .` plus `uvx ruff format --check .` for Python changes.
- CI currently has no test job.
