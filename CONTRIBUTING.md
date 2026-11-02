# Contributing

Thanks for helping with Ubi Ludus. This file is short on purpose; the planning rules live in the [README](README.md#how-we-plan-work).

## Propose a change

1. Find or open an issue first. Tasks, status and priorities are tracked in [Issues](../../issues) and on the project board.
2. Create a branch from `main`. Name it after the task, for example `m1-03-football-data-adapter`.
3. Make the change, with tests where code is involved.
4. Run the checks locally (see [Development](README.md#development)): `ruff check .`, `ruff format .`, `mypy`, `pytest`.
5. Open a pull request that mentions the issue (`Closes #12`). CI must pass before merging.

## Standards

- **Code:** Python 3.12, type hints everywhere, formatted and linted with ruff, strict mypy, at least 80% line coverage on pipeline code.
- **Times:** always timezone-aware. Store UTC, display `America/Sao_Paulo` (PRD FR-06).
- **Documentation:** English. Product UI text is Brazilian Portuguese and lives in one string file.
- **Decisions:** record meaningful architecture decisions as short ADRs in `docs/adr/`.
- **Scope:** ideas outside the current plan go to an issue with the `backlog` label, not into the code.

## Secrets and data

- Never commit API keys, tokens or e-mail addresses. Use `.env` locally (ignored by git) and GitHub Secrets in CI.
- Do not add raw responses from data providers to the repository. Their terms may not allow republishing; see [docs/research/provider-comparison.md](docs/research/provider-comparison.md). Trim test fixtures by hand to the minimum needed.
- No team crests or logos. Use team names and colours only.

## Reporting a problem

Wrong broadcast information is the most useful report you can send. Open an issue with the match, the date and the correct broadcaster, ideally with a link to the official source.
