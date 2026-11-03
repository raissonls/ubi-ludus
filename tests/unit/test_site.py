"""The static site's baseline: security, privacy, strings, size and contrast.

These checks read the files in site/ without a browser, so they run everywhere in a second. The
checks that need a real browser (axe, console errors, requests) are in tests/browser/.
"""

import gzip
import json
import re
from collections.abc import Iterator
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
INDEX = SITE / "index.html"

# Budgets (PRD NFR performance: total JS 100 KB gzipped). Pages are small on purpose.
JS_BUDGET_GZIP = 100 * 1024
CSS_BUDGET_GZIP = 20 * 1024
PAGE_BUDGET_GZIP = 150 * 1024


class Page(HTMLParser):
    """Collects what the checks below need from one HTML file."""

    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.inline_script_text = False
        self._in_script = False
        self._in_title = False
        self.title = ""
        self.comments: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))
        self._in_script = tag == "script"
        self._in_title = tag == "title"

    def handle_endtag(self, tag: str) -> None:
        self._in_script = False
        self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_script and data.strip():
            self.inline_script_text = True
        if self._in_title:
            self.title += data

    def handle_comment(self, data: str) -> None:
        self.comments.append(data)

    def find(self, tag: str) -> list[dict[str, str | None]]:
        return [attrs for name, attrs in self.tags if name == tag]


@pytest.fixture(scope="module")
def page() -> Page:
    parser = Page()
    parser.feed(INDEX.read_text(encoding="utf-8"))
    return parser


def site_files(*suffixes: str) -> list[Path]:
    return sorted(
        p for p in SITE.rglob("*") if p.is_file() and p.suffix in suffixes and "test" not in p.parts
    )


def gzipped(path: Path) -> int:
    return len(gzip.compress(path.read_bytes(), compresslevel=9))


# --- content security policy ----------------------------------------------------------------------


def csp(page: Page) -> dict[str, list[str]]:
    policies = [
        attrs["content"]
        for attrs in page.find("meta")
        if (attrs.get("http-equiv") or "").lower() == "content-security-policy"
    ]
    assert len(policies) == 1, "exactly one Content Security Policy meta tag"
    directives: dict[str, list[str]] = {}
    for part in (policies[0] or "").split(";"):
        words = part.split()
        if words:
            directives[words[0]] = words[1:]
    return directives


def test_the_policy_allows_nothing_by_default_and_only_this_origin_for_what_the_page_needs(
    page: Page,
) -> None:
    policy = csp(page)
    assert policy["default-src"] == ["'none'"]
    for directive in ("script-src", "style-src", "img-src", "font-src", "connect-src"):
        assert policy[directive] == ["'self'"], directive
    assert policy["base-uri"] == ["'none'"]
    assert policy["form-action"] == ["'none'"]


def test_the_policy_has_no_unsafe_keyword_wildcard_or_host(page: Page) -> None:
    for directive, values in csp(page).items():
        for value in values:
            assert "unsafe" not in value, directive
            assert value != "*", directive
            assert not re.match(r"^(https?:|wss?:|//|data:|blob:)", value), (directive, value)


def test_the_policy_is_the_first_thing_in_the_head_so_it_covers_everything_after_it(
    page: Page,
) -> None:
    head = [(tag, attrs) for tag, attrs in page.tags if tag in {"meta", "link", "script", "title"}]
    first_resource = next(i for i, (tag, _) in enumerate(head) if tag in {"link", "script"})
    policy_at = next(
        i
        for i, (tag, attrs) in enumerate(head)
        if tag == "meta" and (attrs.get("http-equiv") or "").lower() == "content-security-policy"
    )
    assert policy_at < first_resource


def test_no_inline_script_style_or_event_handler(page: Page) -> None:
    assert not page.inline_script_text, "an inline <script> body"
    assert not page.find("style"), "a <style> block"
    for tag, attrs in page.tags:
        assert "style" not in attrs, f"a style attribute on <{tag}>"
        handlers = [name for name in attrs if name.startswith("on")]
        assert not handlers, f"{handlers} on <{tag}>"
        assert not (attrs.get("href") or "").lower().startswith("javascript:")


def test_every_resource_the_page_loads_is_a_relative_path_on_this_origin(page: Page) -> None:
    loaded = [attrs["src"] for attrs in page.find("script")]
    loaded += [attrs["href"] for attrs in page.find("link")]
    loaded += [attrs["src"] for attrs in page.find("img")]
    assert loaded
    for url in loaded:
        assert url is not None
        assert not re.match(r"^([a-z][a-z0-9+.-]*:|//)", url, re.I), url
        assert (SITE / url).is_file(), f"{url} does not exist"


def test_scripts_are_modules_and_nothing_loads_from_a_cdn(page: Page) -> None:
    assert all(attrs.get("type") == "module" for attrs in page.find("script"))
    text = "\n".join(p.read_text(encoding="utf-8") for p in site_files(".html", ".css", ".js"))
    assert not re.search(r"@import|@font-face", text), "fonts are the system's; no @import"
    assert not re.search(r"url\(\s*['\"]?(https?:|//)", text)
    assert not re.search(r"\b(?:import|from)\s*\(?\s*['\"]https?:", text)


def test_external_links_open_safely_and_go_only_to_known_places(page: Page) -> None:
    allowed = (
        "https://github.com/raissonls/ubi-ludus",
        "https://www.football-data.org/",
        "https://www.api-football.com/",
    )
    for attrs in page.find("a"):
        href = attrs.get("href") or ""
        if re.match(r"^(https?:)?//", href):
            assert href.startswith(allowed), href
            assert "noopener" in (attrs.get("rel") or ""), href
            assert "noreferrer" in (attrs.get("rel") or ""), href


def test_the_code_never_builds_html_or_runs_text_as_code() -> None:
    forbidden = re.compile(
        r"\.innerHTML|\.outerHTML|insertAdjacentHTML|document\.write|\beval\s*\(|new\s+Function\b"
        r"|setTimeout\s*\(\s*['\"]|setInterval\s*\(\s*['\"]|createContextualFragment"
    )
    for path in site_files(".js"):
        assert not forbidden.search(path.read_text(encoding="utf-8")), path.name


def test_the_code_stores_nothing_and_sets_no_cookie_yet() -> None:
    """Preferences arrive in M3-02, in one module; until then nothing may touch storage."""
    for path in site_files(".js"):
        text = path.read_text(encoding="utf-8")
        assert "document.cookie" not in text, path.name
        assert not re.search(r"localStorage|sessionStorage|indexedDB", text), path.name


# --- page structure ------------------------------------------------------------------------------


def test_the_page_declares_its_language_viewport_and_title(page: Page) -> None:
    [html] = page.find("html")
    assert html["lang"] == "pt-BR"
    viewport = next(a for a in page.find("meta") if a.get("name") == "viewport")
    assert "width=device-width" in (viewport["content"] or "")
    assert "user-scalable=no" not in (viewport["content"] or "")  # never block zoom
    assert page.title.strip()
    description = next(a for a in page.find("meta") if a.get("name") == "description")
    assert (description["content"] or "").strip()


def test_the_page_has_one_h1_and_the_three_landmarks(page: Page) -> None:
    names = [tag for tag, _ in page.tags]
    assert names.count("h1") == 1
    for landmark in ("header", "main", "footer"):
        assert names.count(landmark) == 1, landmark


def test_the_first_focusable_element_skips_to_the_main_region(page: Page) -> None:
    first_link = next(attrs for tag, attrs in page.tags if tag == "a")
    assert first_link["href"] == "#main"
    main = page.find("main")[0]
    assert main["id"] == "main"
    assert main.get("tabindex") == "-1"  # so the skip link can move focus there


def test_both_themes_and_reduced_motion_are_handled_in_the_styles() -> None:
    tokens = (SITE / "css" / "tokens.css").read_text(encoding="utf-8")
    assert "prefers-color-scheme: dark" in tokens
    assert "prefers-reduced-motion: reduce" in tokens
    page_text = INDEX.read_text(encoding="utf-8")
    assert 'name="color-scheme" content="light dark"' in page_text


# --- strings -------------------------------------------------------------------------------------


def flatten(node: dict[str, object], prefix: str = "") -> Iterator[tuple[str, object]]:
    for key, value in node.items():
        if isinstance(value, dict):
            yield from flatten(value, f"{prefix}{key}.")
        else:
            yield f"{prefix}{key}", value


@pytest.fixture(scope="module")
def strings() -> dict[str, object]:
    return dict(flatten(json.loads((SITE / "i18n" / "pt-BR.json").read_text(encoding="utf-8"))))


def test_every_string_key_the_page_uses_exists(page: Page, strings: dict[str, object]) -> None:
    used = [attrs["data-i18n"] for _, attrs in page.tags if "data-i18n" in attrs]
    assert used
    assert [key for key in used if key not in strings] == []
    for _, attrs in page.tags:
        for pair in (attrs.get("data-i18n-attr") or "").split(";"):
            if ":" in pair:
                assert pair.split(":")[1].strip() in strings, pair


def test_every_string_in_the_file_is_used_by_the_page_or_the_code(
    page: Page, strings: dict[str, object]
) -> None:
    """Dead strings pile up. Strings for views that do not exist yet are added with the view."""
    used = {attrs["data-i18n"] for _, attrs in page.tags if "data-i18n" in attrs}
    code = "\n".join(p.read_text(encoding="utf-8") for p in site_files(".js"))
    unused = [k for k in strings if k not in used and f"'{k}'" not in code]
    assert unused == []


def test_the_page_holds_no_visible_text_of_its_own_except_the_no_script_notice(
    page: Page,
) -> None:
    visible = re.sub(
        r"<!--.*?-->|<head>.*?</head>|<script.*?</script>",
        "",
        INDEX.read_text(encoding="utf-8"),
        flags=re.S,
    )
    visible = re.sub(r"<noscript>.*?</noscript>", "", visible, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", visible)
    assert text.split() == [], "visible text belongs in i18n/pt-BR.json"


def test_the_footer_carries_the_data_attributions(strings: dict[str, object]) -> None:
    """football-data.org's terms require this exact line; API-Football is a courtesy."""
    assert (
        strings["footer.attribution.footballData"]
        == "Football data provided by the Football-Data.org API"
    )
    assert "API-Football" in str(strings["footer.attribution.apiFootball"])
    html = INDEX.read_text(encoding="utf-8")
    assert "https://www.football-data.org/" in html
    assert "https://www.api-football.com/" in html


def test_the_footer_has_a_privacy_notice_and_the_repository_has_a_privacy_file(
    strings: dict[str, object],
) -> None:
    notice = str(strings["footer.privacy"]).lower()
    assert "cookies" in notice and "navegador" in notice
    assert "PRIVACY.md" in INDEX.read_text(encoding="utf-8")
    privacy = (ROOT / "PRIVACY.md").read_text(encoding="utf-8")
    for promise in ("No accounts", "no cookies", "localStorage", "No third-party requests"):
        assert promise.lower() in privacy.lower(), promise


# --- size ----------------------------------------------------------------------------------------


def test_javascript_and_css_stay_inside_their_budgets() -> None:
    js = sum(gzipped(p) for p in site_files(".js"))
    css = sum(gzipped(p) for p in site_files(".css"))
    assert js <= JS_BUDGET_GZIP, f"JS is {js} bytes gzipped, the budget is {JS_BUDGET_GZIP}"
    assert css <= CSS_BUDGET_GZIP, f"CSS is {css} bytes gzipped, the budget is {CSS_BUDGET_GZIP}"


def test_the_whole_page_stays_inside_its_budget() -> None:
    total = sum(gzipped(p) for p in site_files(".html", ".css", ".js", ".json", ".svg"))
    assert total <= PAGE_BUDGET_GZIP, (
        f"the site is {total} bytes gzipped, the budget is {PAGE_BUDGET_GZIP}"
    )


def test_no_file_in_the_site_is_a_surprise() -> None:
    allowed = {".html", ".css", ".js", ".json", ".svg", ".md"}
    strange = [p.name for p in SITE.rglob("*") if p.is_file() and p.suffix not in allowed]
    assert strange == [], "binary assets (fonts, images) need a decision, not an accident"


# --- contrast (WCAG 2.2 AA) ----------------------------------------------------------------------


def parse_tokens(css: str) -> dict[str, str]:
    return dict(re.findall(r"(--[a-z0-9-]+):\s*(#[0-9a-fA-F]{6})", css))


def themes() -> dict[str, dict[str, str]]:
    css = (SITE / "css" / "tokens.css").read_text(encoding="utf-8")
    dark_start = css.index("prefers-color-scheme: dark")
    dark_end = css.index("prefers-reduced-motion")
    light = parse_tokens(css[:dark_start])
    dark = {**light, **parse_tokens(css[dark_start:dark_end])}
    return {"light": light, "dark": dark}


def luminance(hex_colour: str) -> float:
    def channel(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a: str, b: str) -> float:
    lighter, darker = sorted((luminance(a), luminance(b)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


TEXT_PAIRS = [
    ("--color-text", "--color-bg"),
    ("--color-text", "--color-surface"),
    ("--color-text-muted", "--color-bg"),
    ("--color-text-muted", "--color-surface"),
    ("--color-link", "--color-bg"),
    ("--color-link", "--color-surface"),
    ("--color-on-accent", "--color-accent"),
    ("--color-confirmed-fg", "--color-confirmed-bg"),
    ("--color-rule-fg", "--color-rule-bg"),
    ("--color-unknown-fg", "--color-unknown-bg"),
    ("--color-live-fg", "--color-live-bg"),
    ("--color-warning-fg", "--color-warning-bg"),
]
# Not text, but meant to be seen: the edge of a control and the focus ring need 3:1 (WCAG 1.4.11).
GRAPHIC_PAIRS = [
    ("--color-border-strong", "--color-surface"),
    ("--color-border-strong", "--color-bg"),
    ("--color-focus", "--color-bg"),
    ("--color-focus", "--color-surface"),
]


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize(("foreground", "background"), TEXT_PAIRS)
def test_text_colours_have_at_least_4_5_to_1_contrast(
    theme: str, foreground: str, background: str
) -> None:
    colours = themes()[theme]
    ratio = contrast(colours[foreground], colours[background])
    assert ratio >= 4.5, f"{theme}: {foreground} on {background} is {ratio:.2f}:1"


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize(("foreground", "background"), GRAPHIC_PAIRS)
def test_borders_and_focus_rings_have_at_least_3_to_1_contrast(
    theme: str, foreground: str, background: str
) -> None:
    colours = themes()[theme]
    ratio = contrast(colours[foreground], colours[background])
    assert ratio >= 3.0, f"{theme}: {foreground} on {background} is {ratio:.2f}:1"


def test_the_dark_theme_changes_every_colour_the_light_theme_defines() -> None:
    light, dark = themes()["light"], themes()["dark"]
    unchanged = [
        name for name in light if name.startswith("--color-") and light[name] == dark[name]
    ]
    assert unchanged == []
