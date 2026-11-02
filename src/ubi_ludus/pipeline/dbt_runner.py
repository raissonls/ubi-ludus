"""Run dbt from Python against a DuckDB file.

Python loads the raw tables, closes its connection, then calls :func:`run_dbt`. A failing model
or data test raises :class:`DbtBuildError`, which stops the pipeline before anything is published.
"""

from __future__ import annotations

import os
from pathlib import Path

from dbt.cli.main import dbtRunner

DBT_DIR = Path(__file__).resolve().parents[3] / "dbt"


class DbtBuildError(RuntimeError):
    """dbt reported a failure. ``failed`` lists the models or tests that failed."""

    def __init__(self, failed: list[str], detail: str = "") -> None:
        self.failed = failed
        names = ", ".join(failed) if failed else "dbt could not start"
        super().__init__(f"dbt build failed: {names}{f' ({detail})' if detail else ''}")


def run_dbt(
    database: Path,
    *,
    project_dir: Path = DBT_DIR,
    work_dir: Path | None = None,
    select: str | None = None,
) -> None:
    """Run ``dbt build`` (models and tests) on ``database``.

    ``work_dir`` is where dbt writes its logs and compiled files. It defaults to the project's
    git-ignored ``target`` and ``logs`` folders; tests pass a temporary folder instead.
    """
    args = [
        "build",
        "--project-dir", str(project_dir),
        "--profiles-dir", str(project_dir),
        "--quiet",
    ]  # fmt: skip
    if work_dir is not None:
        args += ["--target-path", str(work_dir / "target"), "--log-path", str(work_dir / "logs")]
    if select:
        args += ["--select", select]

    previous = os.environ.get("UBI_LUDUS_DB")
    os.environ["UBI_LUDUS_DB"] = str(database.resolve())
    try:
        outcome = dbtRunner().invoke(args)
    finally:
        if previous is None:
            os.environ.pop("UBI_LUDUS_DB", None)
        else:
            os.environ["UBI_LUDUS_DB"] = previous

    if outcome.success:
        return
    if outcome.exception is not None:
        raise DbtBuildError([], str(outcome.exception)) from outcome.exception
    results = getattr(outcome.result, "results", [])
    failed = [str(r.node.name) for r in results if str(r.status) in ("fail", "error")]
    raise DbtBuildError(failed)
