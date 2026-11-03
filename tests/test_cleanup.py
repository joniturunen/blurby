import threading
from datetime import datetime, timedelta

from blurby.cleanup import CleanUpCrew, clean_up_once, delete_expired
from blurby.models import Data, db


def add_secret(sha_link, age):
    db.session.add(
        Data(
            sha_link=sha_link,
            data="secret",
            creator="anonymous",
            timestamp=datetime.now() - age,
        )
    )
    db.session.commit()


def stored_links():
    return sorted(data.sha_link for data in Data.query.all())


def test_delete_expired_removes_only_secrets_older_than_the_ttl(app):
    app.config["BLURBY_TTL_HOURS"] = 48
    add_secret("expired", timedelta(hours=49))
    add_secret("fresh", timedelta(hours=47))

    assert delete_expired() == 1
    assert stored_links() == ["fresh"]


def test_delete_expired_uses_the_configured_ttl(app):
    app.config["BLURBY_TTL_HOURS"] = 1
    add_secret("two-hours-old", timedelta(hours=2))
    add_secret("half-an-hour-old", timedelta(minutes=30))

    assert delete_expired() == 1
    assert stored_links() == ["half-an-hour-old"]


def test_delete_expired_without_expired_secrets_deletes_nothing(app):
    add_secret("fresh", timedelta(minutes=1))

    assert delete_expired() == 0
    assert stored_links() == ["fresh"]


def test_clean_up_once_pushes_its_own_app_context(app):
    add_secret("expired", timedelta(days=3))

    # Like the real background thread, a new thread has no app context.
    worker = threading.Thread(target=clean_up_once, args=(app,))
    worker.start()
    worker.join(timeout=5)

    assert stored_links() == []


def test_clean_up_crew_runs_cleanup_passes_in_a_background_thread(app, monkeypatch):
    ran = threading.Event()
    monkeypatch.setattr("blurby.cleanup.clean_up_once", lambda _app: ran.set())
    app.config["BLURBY_CLEANUP_INTERVAL"] = 3600

    CleanUpCrew(app)

    assert ran.wait(timeout=5)
