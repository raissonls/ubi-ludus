# Ubi Ludus

*Ubi ludus?* is Latin for "where is the game?". Ubi Ludus answers that question for Brazilian football fans: which TV channel or streaming service carries each match in Brazil, shown on a free static website and in a daily morning e-mail.

**Status:** Phase 1 planning. No code yet. The repository is private for now and goes public after the planning milestone closes, targeting 9 November 2026. The plan and the checklist for that day are in [docs/security-checklist.md](docs/security-checklist.md).

## Where things are

| What | Where |
|---|---|
| Product requirements (Phase 1) | [docs/PRD.md](docs/PRD.md) |
| Tasks, status and progress | [Issues](../../issues) and the [Ubi Ludus project board](https://github.com/users/raissonls/projects/1) |
| Milestones M0 to M5 and their due dates | [Milestones](../../milestones) |
| Ideas outside the current plan | Issues labeled [`backlog`](../../issues?q=label%3Abacklog) |
| How it fits together | [docs/architecture.md](docs/architecture.md) |
| Why we chose it (architecture decisions) | [docs/adr/](docs/adr/README.md) |
| Providers: coverage, limits, terms | [docs/research/provider-comparison.md](docs/research/provider-comparison.md) |
| Security and the go-public plan | [docs/security-checklist.md](docs/security-checklist.md) |

## Phase 1 at a glance

- **Goal:** answer "where can I watch my team's next matches?" in under 10 seconds, at R$ 0/month.
- **Timeline:** 7 weeks, milestones M0 to M5, target launch 2026-12-20.
- **Languages:** documentation in English, product UI in Brazilian Portuguese (pt-BR).

## How we plan work

Each kind of information has **one home**, so nothing has to be kept in sync by hand.

- **The PRD is the "what and why".** It lives in [docs/PRD.md](docs/PRD.md). Changes go through a pull request.
- **Tasks are GitHub issues.** Each issue holds the reason for the task, a "definition of done" checklist, the PRD requirement IDs it covers (for example `FR-01`) and what it depends on.
- **The project board shows status.** The columns are Todo, In Progress and Done.
- **Milestones group the work.** M0 to M5 follow the timeline in the PRD, and each one shows its own progress.

### Reading an issue

| Part | Meaning |
|---|---|
| **Title** `M2-02 · Rights resolution engine` | Milestone number, task number, short name |
| **Label** `must` / `should` / `could` | Priority (MoSCoW, as in the PRD) |
| **Milestone** | When the task is planned |
| **Estimate (h)** on the board | Planned hours |
| **Blocked by** | Tasks that must be done first |
| **Checklist** | The definition of done. Tick the boxes as the work gets done. |

### Working on a task

1. Open the board and pick a task from **Todo** that is not blocked by an open task. Work through the milestones in order.
2. Move the card to **In Progress** and assign yourself.
3. Do the work in a branch and open a pull request that mentions the issue (for example `Closes #12`).
4. Tick the checklist as you go. Record decisions and findings as comments on the issue.
5. When every box is ticked and the pull request is merged, the issue closes and the card moves to **Done**.

Add the `blocked` label and a comment saying why when a task is stuck waiting on something.

### Changing the plan

- **New idea that is not in the PRD:** open an issue and give it the `backlog` label. It stays out of the board until someone decides to pull it in. This keeps Phase 2 ideas from creeping into Phase 1.
- **Changing requirements:** update `docs/PRD.md` first, in a pull request, then update or create the affected issues.
- **Running out of time:** cut `should` tasks first, then `must` tasks only after talking about it. `could` items live in the backlog.
- **A task is too big:** split it into smaller issues. A good task takes one or two sittings (1 to 5 hours).
- **Task naming:** new tasks follow the pattern `M<milestone>-<nn> · Short name`, and set the milestone, the priority label and the estimate on the board.

### Principles

- If something is unclear, say so on the issue before building on it.
- Every **Must** requirement in the PRD must be covered by at least one issue. Search the issues for the requirement ID (for example `FR-12`) to see which.
- Documentation is written in English.

## Development

You need Python 3.12 and Git. Everything below runs from the repository root.

**First-time setup**

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows (Git Bash: source .venv/Scripts/activate; macOS/Linux: source .venv/bin/activate)
pip install -e ".[dev]"
pre-commit install
```

**Daily commands**

| What | Command |
|---|---|
| Lint | `ruff check .` |
| Format | `ruff format .` |
| Type-check | `mypy` |
| Tests with coverage (at least 80% required) | `pytest` |
| Everything pre-commit runs, on all files | `pre-commit run --all-files` |

**Secrets:** copy `.env.example` to `.env` and fill in your own API keys. `.env` is ignored by git. Keys must never be committed; in CI they come from GitHub Secrets. A secret scan runs on every commit through pre-commit.

**Layout**

```text
src/ubi_ludus/pipeline/   data pipeline (providers, normalise, enrich, publish)
src/ubi_ludus/email/      daily e-mail
dbt/                      dbt project: models and data-quality tests on DuckDB
site/                     static website
config/  data/rights/     owner config and the rights table
schemas/                  JSON Schemas
tests/                    unit/, fixtures/, e2e/
docs/                     PRD, research, architecture decisions (adr/)
```

**CI:** every pull request runs the same checks on GitHub Actions (lint, format, type-check, tests, plus a secret scan). Dependabot opens weekly update pull requests for GitHub Actions and Python packages. Third-party actions are pinned to commit SHAs, and each workflow job requests only the permissions it needs.

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to propose a change.

## License

Copyright 2026 Raisson Leal Silva. The code is licensed under the [Apache License 2.0](LICENSE). The licence covers our code only: data from third-party providers keeps its own terms (see [docs/research/provider-comparison.md](docs/research/provider-comparison.md)).
