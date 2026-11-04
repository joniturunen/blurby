"""At startup, Blurby logs the risks it can't check for itself: who may set
the username header, HTTPS and rate limits, the storage limit and root."""

import logging

import pytest

from blurby import create_app
from blurby.main import SECURITY_NOTES, log_security_notes


def notes(caplog, monkeypatch, euid=5678, **config):
    monkeypatch.setattr("os.geteuid", lambda: euid)
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", **config})
    with caplog.at_level(logging.INFO, logger="blurby.main"):
        log_security_notes(app)
    return caplog.records


def warnings(records):
    return [r.getMessage() for r in records if r.levelno == logging.WARNING]


def test_the_username_header_must_be_set_or_removed_by_the_proxy(caplog, monkeypatch):
    [header, _] = warnings(notes(caplog, monkeypatch))

    assert "'username' request header" in header
    assert "replacing any value a client sent" in header
    assert "BLURBY_USERNAME_HEADER" in header


def test_names_the_configured_header(caplog, monkeypatch):
    [header, _] = warnings(
        notes(caplog, monkeypatch, BLURBY_USERNAME_HEADER="X-Forwarded-User")
    )

    assert "'X-Forwarded-User' request header" in header


def test_without_a_username_header_there_is_nothing_to_warn_about(caplog, monkeypatch):
    records = notes(caplog, monkeypatch, BLURBY_USERNAME_HEADER="")

    assert not any("request header" in message for message in warnings(records))
    assert "everyone is anonymous" in caplog.text


def test_points_to_https_and_rate_limits(caplog, monkeypatch):
    [_, proxy] = warnings(notes(caplog, monkeypatch))

    assert "HTTPS" in proxy
    assert "Strict-Transport-Security" in proxy
    assert "rate-limits" in proxy
    assert SECURITY_NOTES in proxy


def test_warns_when_the_storage_limit_is_off(caplog, monkeypatch):
    records = notes(caplog, monkeypatch, BLURBY_MAX_SECRETS=0)

    assert any("BLURBY_MAX_SECRETS is 0" in message for message in warnings(records))


def test_says_nothing_about_a_storage_limit_that_is_on(caplog, monkeypatch):
    notes(caplog, monkeypatch)

    assert "BLURBY_MAX_SECRETS" not in caplog.text


@pytest.mark.parametrize(("euid", "warned"), [(0, True), (5678, False)])
def test_warns_when_running_as_root(caplog, monkeypatch, euid, warned):
    notes(caplog, monkeypatch, euid=euid)

    assert ("runs as root" in caplog.text) is warned
