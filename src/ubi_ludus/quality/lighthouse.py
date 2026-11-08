"""Hold the site to its speed and weight targets (PRD NFR performance, S8, M5-02).

The targets, for a phone on a simulated 4G connection (Lighthouse's mobile mode):

* Lighthouse **90 or more** in Performance, Accessibility, Best Practices and SEO;
* **Largest Contentful Paint** at most 2.5 s;
* **Layout shift** (CLS) at most 0.1: the page must not jump while it loads;
* **Total JavaScript** at most 100 KB, gzipped (what is sent over the network).

Two commands, standard library only (the CI job runs them without installing anything):

``serve``  serves ``site/`` on a local port the way GitHub Pages does (gzip, ten minutes of cache),
           with a data folder in place of the pipeline's, so Lighthouse sees what a visitor gets.
``check``  reads Lighthouse's JSON reports (it is run several times, because one run varies), takes
           the middle value of each number, prints a table and exits 1 if any target is missed.
"""

from __future__ import annotations

import argparse
import functools
import gzip
import http.server
import json
import statistics
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

CATEGORIES = ("performance", "accessibility", "best-practices", "seo")
#: What GitHub Pages sends for a static file, so a local run behaves like the real thing.
CACHE_CONTROL = "max-age=600"
_COMPRESSIBLE = (".html", ".css", ".js", ".json", ".svg", ".txt", ".xml")
_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".txt": "text/plain; charset=utf-8",
    ".xml": "application/xml",
}


@dataclass(frozen=True)
class Budget:
    min_score: float = 0.90
    max_lcp_ms: float = 2500.0
    max_cls: float = 0.1
    max_tbt_ms: float = 200.0
    max_js_kb: float = 100.0


BUDGET = Budget()


@dataclass(frozen=True)
class Measured:
    scores: dict[str, float]
    lcp_ms: float
    cls: float
    tbt_ms: float
    js_kb: float


def measure(report: dict[str, Any]) -> Measured:
    """The numbers of one Lighthouse report that the targets are about."""
    audits = report["audits"]
    scripts = [
        item["transferSize"]
        for item in audits["network-requests"]["details"]["items"]
        if item.get("resourceType") == "Script"
    ]
    return Measured(
        scores={name: float(report["categories"][name]["score"]) for name in CATEGORIES},
        lcp_ms=float(audits["largest-contentful-paint"]["numericValue"]),
        cls=float(audits["cumulative-layout-shift"]["numericValue"]),
        tbt_ms=float(audits["total-blocking-time"]["numericValue"]),
        js_kb=sum(scripts) / 1024,
    )


def middle(runs: Sequence[Measured]) -> Measured:
    """The middle value of each number over several runs: one slow run does not fail the build."""
    return Measured(
        scores={n: statistics.median(r.scores[n] for r in runs) for n in CATEGORIES},
        lcp_ms=statistics.median(r.lcp_ms for r in runs),
        cls=statistics.median(r.cls for r in runs),
        tbt_ms=statistics.median(r.tbt_ms for r in runs),
        js_kb=statistics.median(r.js_kb for r in runs),
    )


def problems(found: Measured, budget: Budget = BUDGET) -> list[str]:
    """What is over the budget, one line each, in words."""
    out = [
        f"{name} is {round(score * 100)}, the target is {round(budget.min_score * 100)} or more"
        for name, score in found.scores.items()
        if score < budget.min_score
    ]
    if found.lcp_ms > budget.max_lcp_ms:
        out.append(
            f"Largest Contentful Paint is {found.lcp_ms / 1000:.2f} s, "
            f"the target is {budget.max_lcp_ms / 1000:g} s or less"
        )
    if found.cls > budget.max_cls:
        out.append(f"layout shift is {found.cls:.3f}, the target is {budget.max_cls:g} or less")
    if found.tbt_ms > budget.max_tbt_ms:
        out.append(
            f"blocking time is {found.tbt_ms:.0f} ms, the target is {budget.max_tbt_ms:g} or less"
        )
    if found.js_kb > budget.max_js_kb:
        out.append(
            f"JavaScript is {found.js_kb:.1f} KB gzipped, "
            f"the target is {budget.max_js_kb:g} or less"
        )
    return out


def table(found: Measured, budget: Budget = BUDGET, runs: int = 1) -> str:
    """The numbers as a Markdown table, for the run's summary page."""
    rows = [
        (
            name.replace("-", " ").title(),
            f"{round(s * 100)}",
            f"{round(budget.min_score * 100)} or more",
            s >= budget.min_score,
        )
        for name, s in found.scores.items()
    ]
    rows += [
        (
            "Largest Contentful Paint",
            f"{found.lcp_ms / 1000:.2f} s",
            f"{budget.max_lcp_ms / 1000:g} s or less",
            found.lcp_ms <= budget.max_lcp_ms,
        ),
        (
            "Layout shift",
            f"{found.cls:.3f}",
            f"{budget.max_cls:g} or less",
            found.cls <= budget.max_cls,
        ),
        (
            "Total blocking time",
            f"{found.tbt_ms:.0f} ms",
            f"{budget.max_tbt_ms:g} ms or less",
            found.tbt_ms <= budget.max_tbt_ms,
        ),
        (
            "JavaScript, gzipped",
            f"{found.js_kb:.1f} KB",
            f"{budget.max_js_kb:g} KB or less",
            found.js_kb <= budget.max_js_kb,
        ),
    ]
    lines = [
        f"Lighthouse, mobile, simulated 4G: the middle of {runs} run(s).",
        "",
        "| Measure | Found | Target | |",
        "| --- | --- | --- | --- |",
    ]
    lines += [f"| {n} | {v} | {t} | {'ok' if ok else '**over**'} |" for n, v, t, ok in rows]
    return "\n".join(lines) + "\n"


def check(paths: Sequence[Path], budget: Budget = BUDGET) -> tuple[str, list[str]]:
    """Read the reports. Returns the table and the list of what is over the budget."""
    runs = [measure(json.loads(path.read_text(encoding="utf-8"))) for path in paths]
    if not runs:
        raise ValueError("no Lighthouse report to read")
    found = middle(runs)
    return table(found, budget, len(runs)), problems(found, budget)


# --- the local server ---------------------------------------------------------------------------


class PagesLikeHandler(http.server.SimpleHTTPRequestHandler):
    """Static files, compressed and cached the way GitHub Pages sends them."""

    data_dir: Path | None = None

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - the base class name
        return

    def translate_path(self, path: str) -> str:
        clean = urlparse(path).path
        if self.data_dir is not None and clean.startswith("/data/"):
            return str(self.data_dir / clean.removeprefix("/data/"))
        return super().translate_path(path)

    def do_GET(self) -> None:  # noqa: N802 - the name the base class calls
        path = Path(self.translate_path(self.path))
        if path.is_dir():
            path = path / "index.html"
        if not path.is_file() or path.suffix not in _COMPRESSIBLE:
            super().do_GET()
            return
        body = path.read_bytes()
        headers = {
            "Content-Type": _TYPES[path.suffix],
            "Cache-Control": CACHE_CONTROL,
        }
        if "gzip" in self.headers.get("Accept-Encoding", ""):
            body = gzip.compress(body, 6)
            headers["Content-Encoding"] = "gzip"
        self.send_response(200)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def make_server(site: Path, data: Path | None, port: int) -> http.server.ThreadingHTTPServer:
    """A server for ``site`` (and ``data`` as ``/data/``) on 127.0.0.1. Port 0 picks a free one."""
    handler = type("Handler", (PagesLikeHandler,), {"data_dir": data})
    return http.server.ThreadingHTTPServer(
        ("127.0.0.1", port), functools.partial(handler, directory=str(site))
    )


def serve(site: Path, data: Path | None, port: int) -> None:
    """Serve until stopped."""
    server = make_server(site, data, port)
    print(f"Serving {site} on http://127.0.0.1:{port}/", flush=True)  # noqa: T201
    server.serve_forever()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    commands = parser.add_subparsers(dest="command", required=True)
    serving = commands.add_parser("serve", help="serve the site the way GitHub Pages does")
    serving.add_argument("--site", type=Path, default=Path("site"))
    serving.add_argument("--data", type=Path, default=None, help="a folder to serve as /data/")
    serving.add_argument("--port", type=int, default=8765)
    checking = commands.add_parser("check", help="hold Lighthouse reports to the targets")
    checking.add_argument("reports", nargs="+", type=Path)
    args = parser.parse_args(argv)

    if args.command == "serve":
        serve(args.site, args.data, args.port)
        return 0
    summary, over = check(args.reports)
    print(summary)  # noqa: T201
    for line in over:
        print(f"over the target: {line}", file=sys.stderr)  # noqa: T201
    return 1 if over else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
