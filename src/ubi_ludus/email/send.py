"""Send the morning e-mail (PRD FR-40, FR-41, FR-42).

The mail goes through SMTP, which every provider offers (Brevo, a Gmail app password, Resend), so
the code does not depend on one: the provider is whatever the secrets point at. The address and the
credentials are read from the environment only (GitHub Secrets in CI, a git-ignored ``.env`` on your
own machine) and are never written to a file, a log or an error message.

Run it with ``python -m ubi_ludus.email.send``; ``--dry-run`` does everything but send.
"""

from __future__ import annotations

import os
import smtplib
import ssl
import sys
from argparse import ArgumentParser
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr
from pathlib import Path
from typing import Literal

from ubi_ludus.email.briefing import Briefing, build_briefing, load_documents
from ubi_ludus.email.render import RenderedEmail, render_briefing
from ubi_ludus.pipeline.env import load_env_file
from ubi_ludus.pipeline.owner import OwnerConfig, load_owner
from ubi_ludus.pipeline.window import BRAZIL_TZ

#: The secrets. Without any of them the job fails, naming which (never its value).
REQUIRED_SECRETS = ("SMTP_USER", "SMTP_PASSWORD", "EMAIL_FROM", "EMAIL_TO")
#: Not secret, so they have defaults: Brevo's relay, the port that starts with STARTTLS.
DEFAULT_HOST = "smtp-relay.brevo.com"
DEFAULT_PORT = 587
TIMEOUT_SECONDS = 30

SmtpFactory = Callable[..., smtplib.SMTP]


class EmailConfigError(ValueError):
    """A secret is missing or is not what it should be. The message names it, never its value."""


class EmailSendError(RuntimeError):
    """The mail server refused or could not be reached. The message never holds a credential."""


@dataclass(frozen=True)
class EmailSettings:
    host: str
    port: int
    user: str
    password: str
    sender: str
    recipient: str

    def __repr__(self) -> str:  # a stray print or traceback must not show a secret
        return f"EmailSettings(host={self.host!r}, port={self.port}, user=<hidden>, ...)"

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> EmailSettings:
        """Read the settings, or raise :class:`EmailConfigError` listing everything wrong."""
        env = os.environ if environ is None else environ
        missing = [name for name in REQUIRED_SECRETS if not env.get(name, "").strip()]
        if missing:
            names = ", ".join(missing)
            raise EmailConfigError(
                f"Missing secret(s): {names}. Add them as GitHub Secrets "
                "(Settings > Secrets and variables > Actions) and pass them to the job as "
                "environment variables, or put them in your local .env. See docs/email.md."
            )
        problems = [
            f"{name} is not a single e-mail address"
            for name in ("EMAIL_FROM", "EMAIL_TO")
            if not _is_address(env[name])
        ]
        port_text = env.get("SMTP_PORT", "").strip() or str(DEFAULT_PORT)
        if not port_text.isdigit() or not 0 < int(port_text) < 65536:
            problems.append("SMTP_PORT is not a port number")
        if problems:
            raise EmailConfigError("; ".join(problems) + ". See docs/email.md.")
        return cls(
            host=env.get("SMTP_HOST", "").strip() or DEFAULT_HOST,
            port=int(port_text),
            user=env["SMTP_USER"].strip(),
            password=env["SMTP_PASSWORD"],
            sender=env["EMAIL_FROM"].strip(),
            recipient=env["EMAIL_TO"].strip(),
        )


def _is_address(value: str) -> bool:
    """One plain address: no line break (header injection), no list, text on both sides of @."""
    text = value.strip()
    if not text or any(char in text for char in "\r\n,;<>\x00 "):
        return False
    name, address = parseaddr(text)
    local, _, domain = address.partition("@")
    return not name and address == text and bool(local) and "." in domain


# --- FR-42: send or not ---------------------------------------------------------------------


@dataclass(frozen=True)
class Decision:
    send: bool
    reason: str


def decide(briefing: Briefing, owner: OwnerConfig) -> Decision:
    """Whether to send: a day with something to list always; an empty one as the owner chose."""
    if not briefing.is_empty:
        return Decision(True, "there are matches to list")
    if owner.quiet_days == "note":
        return Decision(True, "no matches, and quiet_days is note")
    return Decision(False, "no matches, and quiet_days is skip")


# --- the message and the sending -------------------------------------------------------------


def build_message(email: RenderedEmail, settings: EmailSettings) -> EmailMessage:
    """A multipart message: plain text first, HTML as the alternative (FR-43)."""
    message = EmailMessage()
    message["Subject"] = email.subject
    message["From"] = settings.sender
    message["To"] = settings.recipient
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid(domain=settings.sender.rpartition("@")[2])
    message["Auto-Submitted"] = "auto-generated"  # a robot, so no auto-replies back to it
    message.set_content(email.text)
    message.add_alternative(email.html, subtype="html")
    return message


def send_message(
    message: EmailMessage,
    settings: EmailSettings,
    *,
    smtp_factory: SmtpFactory | None = None,
) -> None:
    """Hand the message to the mail server over an encrypted connection.

    Port 465 is encrypted from the start; any other port starts plain and must upgrade with
    STARTTLS before the login is sent, or nothing is sent.
    """
    context = ssl.create_default_context()
    implicit = settings.port == 465
    factory: SmtpFactory = smtp_factory or (smtplib.SMTP_SSL if implicit else smtplib.SMTP)
    kwargs: dict[str, object] = {"timeout": TIMEOUT_SECONDS}
    if implicit:
        kwargs["context"] = context
    try:
        with factory(settings.host, settings.port, **kwargs) as server:
            if not implicit:
                server.starttls(context=context)
            server.login(settings.user, settings.password)
            server.send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        raise EmailSendError(
            f"The mail server rejected the login (code {exc.smtp_code}). Check SMTP_USER and "
            "SMTP_PASSWORD, and that the sender in EMAIL_FROM is verified with the provider."
        ) from None
    except (smtplib.SMTPException, OSError) as exc:
        raise EmailSendError(
            f"Could not send through {settings.host}:{settings.port} ({type(exc).__name__}). "
            "Check SMTP_HOST, SMTP_PORT and the provider's status."
        ) from None


# --- the command -----------------------------------------------------------------------------


def run(
    *,
    data: Path,
    now: datetime,
    site_url: str | None,
    dry_run: bool,
    owner: OwnerConfig,
    environ: Mapping[str, str] | None = None,
    smtp_factory: SmtpFactory | None = None,
) -> Literal["sent", "skipped", "dry-run"]:
    """Build today's briefing and send it, unless the owner's rule says to skip."""
    # The secrets are checked first, quiet day or not, so a missing one fails the job the day it
    # goes missing and not on the first day with a match.
    settings = None if dry_run else EmailSettings.from_env(environ)
    briefing = build_briefing(load_documents(data), owner, now)
    decision = decide(briefing, owner)
    if not decision.send:
        return "skipped"
    email = render_briefing(briefing, site_url=site_url)
    if settings is None:
        return "dry-run"
    send_message(build_message(email, settings), settings, smtp_factory=smtp_factory)
    return "sent"


def main(argv: Sequence[str] | None = None) -> int:
    parser = ArgumentParser(description="Send the morning e-mail to the owner.")
    parser.add_argument("--data", type=Path, default=Path("site/data"))
    parser.add_argument("--now", help="a moment in ISO 8601 (default: now)")
    parser.add_argument("--site-url", default=os.environ.get("SITE_URL") or None)
    parser.add_argument("--dry-run", action="store_true", help="decide and render, send nothing")
    args = parser.parse_args(argv)
    load_env_file()  # your own machine only; in CI the variables are already set
    now = (
        datetime.fromisoformat(args.now.replace("Z", "+00:00"))
        if args.now
        else datetime.now(BRAZIL_TZ)
    )
    try:
        outcome = run(
            data=args.data,
            now=now,
            site_url=args.site_url,
            dry_run=args.dry_run,
            owner=load_owner(),
        )
    except (EmailConfigError, EmailSendError) as exc:
        print(f"error: {exc}", file=sys.stderr)  # noqa: T201
        return 1
    messages = {
        "sent": "E-mail sent.",
        "skipped": "No e-mail today: no matches to list and quiet_days is skip.",
        "dry-run": "Dry run: the e-mail was rendered and not sent.",
    }
    print(messages[outcome])  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
