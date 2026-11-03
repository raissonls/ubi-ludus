"""Shared for the browser tests: the site's files, the page load and what it reports."""

import json
from collections.abc import Callable, Iterator
from pathlib import Path

from axe_playwright_python.sync_playwright import Axe  # type: ignore[import-untyped]
from playwright.sync_api import Browser, Page, Request, Route

SITE = Path(__file__).resolve().parents[2] / "site"
# The published files the site loads from /data/. The pipeline writes the real ones; the tests
# serve small hand-written ones (tests/fixtures/site/data, valid against the schemas).
DATA = Path(__file__).resolve().parents[1] / "fixtures" / "site" / "data"
GALLERY = Path(__file__).resolve().parents[1] / "fixtures" / "site" / "gallery"
NOW = "2026-11-02T12:00:00Z"  # the matches of the fixtures are in the days after this
STORAGE_KEY = "ubi-ludus:preferences"
SECRET_TEAM = "time-secreto-xyz"  # noqa: S105 - a marker that must never leave the browser
SECRET_SERVICE = "servico-secreto-xyz"  # noqa: S105 - same
CHOICES = {
    STORAGE_KEY: json.dumps({"version": 1, "teams": [SECRET_TEAM], "services": [SECRET_SERVICE]})
}
STORAGE_BLOCKED = (
    "Object.defineProperty(window, 'localStorage',"
    " { get() { throw new DOMException('denied', 'SecurityError'); } });"
)
WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"]
WATCH_VIOLATIONS = (
    "window.__violations = [];"
    "document.addEventListener('securitypolicyviolation',"
    " e => window.__violations.push(e.violatedDirective));"
)
VIEWPORTS = {"desktop": (1280, 800), "mobile": (375, 812), "narrow": (320, 640)}


def answer_with(status: int) -> Callable[[Route], None]:
    return lambda route: route.fulfill(status=status)


class Visit:
    """One page load, with everything the browser reported while it happened."""

    def __init__(self, page: Page, origin: str) -> None:
        self.page = page
        self.origin = origin
        self.console: list[str] = []
        self.requests: list[str] = []
        self.details: list[Request] = []
        self.failed: list[str] = []
        page.on("console", lambda m: self.console.append(f"{m.type}: {m.text}"))
        page.on("pageerror", lambda e: self.console.append(f"pageerror: {e}"))
        page.on("request", self._saw)
        page.on("requestfailed", lambda r: self.failed.append(r.url))

    def _saw(self, request: Request) -> None:
        self.requests.append(request.url)
        self.details.append(request)

    def open(self) -> None:
        self.page.goto(self.origin + "/index.html")
        self.page.wait_for_selector("html[data-ready='true']")


def visit(
    browser: Browser,
    origin: str,
    scheme: str = "light",
    size: str = "desktop",
    reduced_motion: str = "no-preference",
    saved: dict[str, str] | None = None,
    storage_blocked: bool = False,
    broken: dict[str, int] | None = None,
    newer_format: str | None = None,
) -> Iterator[Visit]:
    """Open the page. ``saved`` is what localStorage holds before the page runs, ``broken`` maps a
    data file to the HTTP status it answers with, `newer_format` names a data file served as if
    it were in a format the site does not know."""
    width, height = VIEWPORTS[size]
    context = browser.new_context(
        color_scheme=scheme,  # type: ignore[arg-type]
        reduced_motion=reduced_motion,  # type: ignore[arg-type]
        viewport={"width": width, "height": height},
    )
    try:
        if saved:
            items = json.dumps(saved)
            context.add_init_script(
                f"for (const [k, v] of Object.entries({items})) localStorage.setItem(k, v);"
            )
        if storage_blocked:
            context.add_init_script(STORAGE_BLOCKED)
        page = context.new_page()
        page.clock.set_fixed_time(NOW)
        for name, status in (broken or {}).items():
            page.route(f"**/data/{name}.json", answer_with(status))
        if newer_format:
            document = json.loads((DATA / f"{newer_format}.json").read_text(encoding="utf-8"))
            document["schema_version"] = "2.0"
            page.route(
                f"**/data/{newer_format}.json",
                lambda route: route.fulfill(
                    status=200, content_type="application/json", body=json.dumps(document)
                ),
            )
        current = Visit(page, origin)
        current.open()
        yield current
    finally:
        context.close()


def axe_violations(page: Page) -> list[str]:
    """What axe finds against WCAG 2.2 AA and best practice, one line per rule."""
    results = Axe().run(page, options={"runOnly": {"type": "tag", "values": WCAG_TAGS}})
    return [
        f"{v['id']} ({v['impact']}): {[n['target'] for n in v['nodes']]}"
        for v in results.response["violations"]
    ]
