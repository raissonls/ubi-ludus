"""Run the pipeline from provider calls to a built warehouse.

The steps: ask the providers (through the cache, the rate limit and the call budget), load
everything Python knows into DuckDB, then let dbt build and test the models. What comes out is a
DuckDB file whose marts are the published files, ready to be exported or queried.

Exporting and publishing are other tasks' work (M4-03). This module stops at the warehouse so that
anything that needs the marts, such as the weekly review report, can use it too.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

from ubi_ludus.pipeline import warehouse
from ubi_ludus.pipeline.config import CompetitionConfig, load_competitions
from ubi_ludus.pipeline.dbt_runner import run_dbt
from ubi_ludus.pipeline.fetch import FetchOutcome, fetch_all, plan_fetches
from ubi_ludus.pipeline.previous import fetch_previous_matches
from ubi_ludus.pipeline.providers.default import default_registry
from ubi_ludus.pipeline.providers.guard import CallLog
from ubi_ludus.pipeline.providers.registry import AdapterRegistry
from ubi_ludus.pipeline.rights import RightsData, load_rights
from ubi_ludus.pipeline.window import today_in_brazil

DEFAULT_TEAMS_PATH: Final = Path(__file__).resolve().parents[3] / "data" / "teams.yml"


class PipelineError(RuntimeError):
    """The pipeline cannot produce a warehouse. The message says what to do."""


@dataclass(frozen=True)
class RunResult:
    database: Path
    outcomes: tuple[FetchOutcome, ...]
    call_log: CallLog

    @property
    def failed_providers(self) -> dict[str, str]:
        """Providers that gave nothing, with why."""
        return {o.provider: o.error for o in self.outcomes if o.error is not None}


def build_warehouse(
    database: Path,
    *,
    now: datetime,
    registry: AdapterRegistry | None = None,
    cache_dir: Path | None = None,
    previous_url: str | None = None,
    teams_path: Path = DEFAULT_TEAMS_PATH,
    competitions: list[CompetitionConfig] | None = None,
    rights: RightsData | None = None,
    work_dir: Path | None = None,
) -> RunResult:
    """Fetch, load and run dbt. Raises :class:`PipelineError` when there is nothing to build on.

    A provider that fails does not stop the run (the others still feed it); the failures are on
    ``RunResult.failed_providers``. dbt tests failing does stop it (``DbtBuildError``), so a bad
    warehouse is never used. ``previous_url`` is where the last published ``matches.json`` is, for
    the reschedule flag; without it nothing is flagged.
    """
    if not teams_path.is_file():
        raise PipelineError(
            f"{teams_path.name} is missing. Without the curated teams no match can be mapped "
            "to our team ids (issue #77)."
        )
    all_competitions = competitions if competitions is not None else load_competitions()
    rights_data = rights if rights is not None else load_rights(competitions=all_competitions)
    today = today_in_brazil(now)

    call_log = CallLog()
    adapters = registry or default_registry(cache_dir=cache_dir, call_log=call_log)
    outcomes = fetch_all(plan_fetches(all_competitions, today), adapters, call_log)
    responses = [response for outcome in outcomes for response in outcome.responses]
    if not responses:
        reasons = "; ".join(f"{o.provider}: {o.error}" for o in outcomes if o.error) or "none asked"
        raise PipelineError(f"No provider gave any data ({reasons})")

    previous = fetch_previous_matches(previous_url) if previous_url else None
    con = warehouse.connect(database)
    try:
        warehouse.load_teams(con, teams_path)
        warehouse.load_competitions(con, all_competitions)
        warehouse.load_provider_responses(con, responses)
        warehouse.load_previous_matches(con, previous)
        warehouse.load_rights_tables(con, rights_data)
    finally:
        con.close()  # DuckDB allows one writer: close before dbt opens the file
    run_dbt(database, work_dir=work_dir, run_at=now, today=today)
    return RunResult(database, tuple(outcomes), call_log)
