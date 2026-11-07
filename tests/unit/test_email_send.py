"""Sending the morning e-mail (FR-40 to FR-42): secrets, skip rule, message and SMTP, no network."""

from __future__ import annotations

import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Any

import pytest
from test_email_briefing import FIXTURES, NOW, documents, match, owner

from ubi_ludus.email import send as send_module
from ubi_ludus.email.briefing import Briefing, build_briefing
from ubi_ludus.email.render import RenderedEmail, render_briefing
from ubi_ludus.email.send import (
    EmailConfigError,
    EmailSendError,
    EmailSettings,
    build_message,
    decide,
    main,
    run,
    send_message,
)

QUIET = datetime(2026, 11, 10, 11, 0, tzinfo=UTC)  # nothing in the fixture data that day
HIDDEN = "s3cret-value-for-tests"
ADDRESS = "someone@example.org"
LOGIN = "login-for-tests"
ENV = {
    "SMTP_USER": LOGIN,
    "SMTP_PASSWORD": HIDDEN,
    "EMAIL_FROM": "sender@example.com",
    "EMAIL_TO": ADDRESS,
}


class FakeSmtp:
    """Records what a real client would have done."""

    calls: list[tuple[str, Any]] = []
    fail_with: Exception | None = None

    def __init__(self, host: str, port: int, **kwargs: Any) -> None:
        FakeSmtp.calls = [("connect", (host, port, sorted(kwargs)))]

    def __enter__(self) -> FakeSmtp:
        return self

    def __exit__(self, *exc: object) -> None:
        FakeSmtp.calls.append(("close", None))

    def starttls(self, **kwargs: Any) -> None:
        FakeSmtp.calls.append(("starttls", sorted(kwargs)))

    def login(self, user: str, password: str) -> None:
        if FakeSmtp.fail_with is not None:
            raise FakeSmtp.fail_with
        FakeSmtp.calls.append(("login", (user, password)))

    def send_message(self, message: EmailMessage) -> None:
        FakeSmtp.calls.append(("send", message))


@pytest.fixture(autouse=True)
def reset() -> None:
    FakeSmtp.calls = []
    FakeSmtp.fail_with = None


def rendered() -> RenderedEmail:
    given = documents([match("a", "palmeiras", "flamengo")])
    return render_briefing(build_briefing(given, owner(), NOW))


def deliver(settings: EmailSettings) -> None:
    send_message(
        build_message(rendered(), settings),
        settings,
        smtp_factory=FakeSmtp,  # type: ignore[arg-type]
    )


def calls() -> list[str]:
    return [name for name, _ in FakeSmtp.calls]


def body(message: EmailMessage, kind: str) -> str:
    part = message.get_body((kind,))
    assert part is not None
    return str(part.get_content())


# --- the secrets --------------------------------------------------------------------------------


def test_the_settings_are_read_from_the_environment() -> None:
    settings = EmailSettings.from_env({**ENV, "SMTP_HOST": "smtp.example.net", "SMTP_PORT": "465"})
    assert (settings.host, settings.port) == ("smtp.example.net", 465)
    assert (settings.user, settings.sender, settings.recipient) == (
        LOGIN,
        "sender@example.com",
        ADDRESS,
    )


def test_the_host_and_port_have_defaults() -> None:
    settings = EmailSettings.from_env(ENV)
    assert (settings.host, settings.port) == ("smtp-relay.brevo.com", 587)


def test_a_missing_secret_fails_naming_it_and_how_to_fix_it() -> None:
    env = {k: v for k, v in ENV.items() if k not in ("SMTP_PASSWORD", "EMAIL_TO")}
    with pytest.raises(EmailConfigError) as caught:
        EmailSettings.from_env(env)
    message = str(caught.value)
    assert "SMTP_PASSWORD, EMAIL_TO" in message
    assert "GitHub Secrets" in message and "docs/email.md" in message
    assert "SMTP_USER" not in message  # only what is missing


def test_an_empty_secret_counts_as_missing() -> None:
    with pytest.raises(EmailConfigError, match="EMAIL_FROM"):
        EmailSettings.from_env({**ENV, "EMAIL_FROM": "  "})


@pytest.mark.parametrize(
    "bad",
    [
        "no-at-sign",
        "a@b",
        "two@example.org, three@example.org",
        "x@example.org\r\nBcc: victim@example.net",
        "Name <x@example.org>",
        "x@example.org;y@example.org",
    ],
)
def test_an_address_that_could_add_a_recipient_or_a_header_is_refused(bad: str) -> None:
    with pytest.raises(EmailConfigError, match="EMAIL_TO is not a single e-mail address"):
        EmailSettings.from_env({**ENV, "EMAIL_TO": bad})


def test_a_bad_port_is_refused() -> None:
    for bad in ("abc", "0", "70000", "-1"):
        with pytest.raises(EmailConfigError, match="SMTP_PORT"):
            EmailSettings.from_env({**ENV, "SMTP_PORT": bad})


def test_the_settings_never_show_a_secret_when_printed_or_in_an_error() -> None:
    settings = EmailSettings.from_env(ENV)
    shown = repr(settings) + str(settings)
    assert HIDDEN not in shown and ADDRESS not in shown and LOGIN not in shown
    with pytest.raises(EmailConfigError) as caught:
        EmailSettings.from_env({**ENV, "EMAIL_TO": f"{ADDRESS}, other@example.org"})
    assert ADDRESS not in str(caught.value)


# --- FR-42: send or skip ------------------------------------------------------------------------


def empty() -> Briefing:
    return build_briefing(documents([]), owner(), NOW)


def test_a_day_with_matches_is_always_sent() -> None:
    full = build_briefing(documents([match("a", "palmeiras", "flamengo")]), owner(), NOW)
    for choice in ("skip", "note"):
        assert decide(full, owner(quiet_days=choice)).send is True


def test_a_quiet_day_is_skipped_when_the_owner_says_skip() -> None:
    decision = decide(empty(), owner(quiet_days="skip"))
    assert decision.send is False and "skip" in decision.reason


def test_a_quiet_day_sends_a_note_when_the_owner_says_note() -> None:
    decision = decide(empty(), owner(quiet_days="note"))
    assert decision.send is True and "note" in decision.reason


def test_skip_is_what_you_get_when_nothing_is_said() -> None:
    assert owner().quiet_days == "skip"


# --- the message -------------------------------------------------------------------------------


def test_the_message_has_text_and_html_and_the_right_headers() -> None:
    settings = EmailSettings.from_env(ENV)
    email = rendered()
    message = build_message(email, settings)
    assert message["Subject"] == email.subject
    assert (message["From"], message["To"]) == ("sender@example.com", ADDRESS)
    assert message["Bcc"] is None and message["Cc"] is None
    assert message["Auto-Submitted"] == "auto-generated"
    assert message["Message-ID"].endswith("@example.com>")
    assert message.get_content_type() == "multipart/alternative"
    kinds = [part.get_content_type() for part in message.iter_parts()]
    assert kinds == ["text/plain", "text/html"]  # plain first, the HTML is the alternative
    assert "Palmeiras x Flamengo" in body(message, "plain")
    assert "<h1" in body(message, "html")


def test_the_message_carries_non_ascii_text_intact() -> None:
    settings = EmailSettings.from_env(ENV)
    email = RenderedEmail("Hoje: São Paulo x Atlético", "<p>ação</p>", "ação")
    message = build_message(email, settings)
    assert "ação" in body(message, "plain")
    assert message["Subject"] == "Hoje: São Paulo x Atlético"
    assert message.as_bytes()  # it serialises, encoded as needed


# --- the sending ------------------------------------------------------------------------------


def test_it_upgrades_to_tls_before_it_logs_in_and_sends() -> None:
    deliver(EmailSettings.from_env(ENV))
    assert calls() == ["connect", "starttls", "login", "send", "close"]
    assert FakeSmtp.calls[0][1][:2] == ("smtp-relay.brevo.com", 587)
    assert FakeSmtp.calls[2][1] == (LOGIN, HIDDEN)


def test_port_465_is_encrypted_from_the_start() -> None:
    deliver(EmailSettings.from_env({**ENV, "SMTP_PORT": "465"}))
    assert "starttls" not in calls() and calls()[1:3] == ["login", "send"]
    assert "context" in FakeSmtp.calls[0][1][2]  # default TLS settings: certificates checked


def test_a_rejected_login_says_what_to_check_and_never_the_password() -> None:
    FakeSmtp.fail_with = smtplib.SMTPAuthenticationError(535, b"bad credentials " + HIDDEN.encode())
    with pytest.raises(EmailSendError) as caught:
        deliver(EmailSettings.from_env(ENV))
    text = str(caught.value)
    assert "535" in text and "SMTP_USER" in text and "EMAIL_FROM" in text
    assert HIDDEN not in text and caught.value.__cause__ is None
    assert "send" not in calls()


def test_a_525_is_not_called_a_wrong_password() -> None:
    FakeSmtp.fail_with = smtplib.SMTPAuthenticationError(525, b"refused " + HIDDEN.encode())
    with pytest.raises(EmailSendError) as caught:
        deliver(EmailSettings.from_env(ENV))
    text = str(caught.value)
    assert "525" in text and "not a wrong password" in text
    assert "Authorised IPs" in text and "activated" in text
    assert HIDDEN not in text


def test_a_server_that_cannot_be_reached_is_reported_without_secrets() -> None:
    FakeSmtp.fail_with = ConnectionRefusedError(HIDDEN)
    with pytest.raises(EmailSendError) as caught:
        deliver(EmailSettings.from_env(ENV))
    assert str(caught.value).startswith("Could not send through smtp-relay.brevo.com:587 (")
    assert HIDDEN not in str(caught.value) and ADDRESS not in str(caught.value)


# --- the whole run --------------------------------------------------------------------------


def run_with(
    now: datetime,
    *,
    quiet: str = "skip",
    dry: bool = False,
    env: dict[str, str] | None = None,
) -> str:
    return run(
        data=FIXTURES,
        now=now,
        site_url=None,
        dry_run=dry,
        owner=owner(teams=("palmeiras",), quiet_days=quiet),
        environ=ENV if env is None else env,
        smtp_factory=FakeSmtp,  # type: ignore[arg-type]
    )


def test_a_day_with_a_match_is_sent_once_to_the_one_recipient() -> None:
    assert run_with(NOW) == "sent"
    sent = [payload for name, payload in FakeSmtp.calls if name == "send"]
    assert len(sent) == 1
    assert sent[0]["To"] == ADDRESS and "Palmeiras x Flamengo" in sent[0]["Subject"]


def test_a_quiet_day_sends_nothing_when_skipping() -> None:
    assert run_with(QUIET) == "skipped"
    assert FakeSmtp.calls == []


def test_a_quiet_day_sends_the_note_when_asked_to() -> None:
    assert run_with(QUIET, quiet="note") == "sent"
    [message] = [payload for name, payload in FakeSmtp.calls if name == "send"]
    assert "Hoje não há jogos" in body(message, "html")
    assert message["Subject"] == "Hoje: sem jogos dos seus times"


def test_a_dry_run_renders_and_sends_nothing_and_needs_no_secret() -> None:
    assert run_with(NOW, dry=True, env={}) == "dry-run"
    assert FakeSmtp.calls == []


def test_a_missing_secret_fails_even_on_a_quiet_day() -> None:
    with pytest.raises(EmailConfigError, match="SMTP_USER"):
        run_with(QUIET, env={k: v for k, v in ENV.items() if k != "SMTP_USER"})
    assert FakeSmtp.calls == []  # and nothing was sent


# --- the command line -------------------------------------------------------------------------


def test_the_command_reports_a_missing_secret_and_exits_with_an_error(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in (*ENV, "SMTP_HOST", "SMTP_PORT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(send_module, "load_env_file", lambda: [])
    code = main(["--data", str(FIXTURES), "--now", "2026-11-03T11:00:00Z"])
    captured = capsys.readouterr()
    assert code == 1
    assert "Missing secret(s): SMTP_USER, SMTP_PASSWORD, EMAIL_FROM, EMAIL_TO" in captured.err
    assert captured.out == ""


def test_the_command_says_when_it_skips_or_sends_and_prints_no_secret(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, value in ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(send_module, "load_env_file", lambda: [])
    monkeypatch.setattr(smtplib, "SMTP", FakeSmtp)
    assert main(["--data", str(FIXTURES), "--now", "2026-11-10T11:00:00Z"]) == 0
    assert "No e-mail today" in capsys.readouterr().out
    assert main(["--data", str(FIXTURES), "--now", "2026-11-03T11:00:00Z"]) == 0
    out = capsys.readouterr()
    assert "E-mail sent." in out.out
    assert all(secret not in out.out + out.err for secret in (HIDDEN, ADDRESS, LOGIN))
    assert main(["--data", str(FIXTURES), "--now", "2026-11-03T11:00:00Z", "--dry-run"]) == 0
    assert "Dry run" in capsys.readouterr().out
