"""Blurby stores at most BLURBY_MAX_SECRETS secrets, so that its database
can't fill the disk; past the limit, new secrets are refused until old ones
expire."""

import logging

import pytest

from blurby import create_app
from blurby.config import load_config
from blurby.models import Data, db


@pytest.mark.parametrize(
    ("value", "limit"), [(None, 10000), ("25", 25), ("0", 0), ("-5", 0)]
)
def test_the_setting(value, limit):
    environ = {} if value is None else {"BLURBY_MAX_SECRETS": value}

    assert load_config(environ)["BLURBY_MAX_SECRETS"] == limit


def test_a_non_numeric_limit_is_rejected():
    with pytest.raises(ValueError):
        load_config({"BLURBY_MAX_SECRETS": "many"})


@pytest.fixture
def make_app():
    apps = []

    def make(limit):
        app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "BLURBY_MAX_SECRETS": limit,
            }
        )
        with app.app_context():
            db.create_all()
        apps.append(app)
        return app

    yield make
    for app in apps:
        with app.app_context():
            db.engine.dispose()


def post(app, text="secret"):
    return app.test_client().post("/", data={"data": text})


def stored(app):
    with app.app_context():
        return db.session.query(Data).count()


def test_past_the_limit_a_new_secret_is_refused(make_app):
    app = make_app(2)

    statuses = [post(app).status_code for _ in range(3)]

    assert statuses == [200, 200, 507]
    assert stored(app) == 2


def test_the_refusal_explains_itself(make_app):
    app = make_app(1)
    post(app)

    response = post(app, "one too many")

    assert response.status_code == 507
    assert b"Blurby is full" in response.data
    assert b"one too many" not in response.data


def test_the_refusal_is_logged_without_the_secret(make_app, caplog):
    app = make_app(1)
    post(app)

    with caplog.at_level(logging.INFO):
        post(app, "TOP-SECRET-VALUE")

    assert "BLURBY_MAX_SECRETS" in caplog.text
    assert "TOP-SECRET-VALUE" not in caplog.text


def test_a_burnt_receipt_counts(make_app):
    app = make_app(1)
    with app.app_context():
        db.session.add(Data(sha_link="b" * 64, data="", creator="anonymous"))
        db.session.commit()

    assert post(app).status_code == 507


def test_deleting_a_secret_makes_room(make_app):
    app = make_app(1)
    with app.app_context():
        db.session.add(Data(sha_link="d" * 64, data="old", creator="anonymous"))
        db.session.commit()
    assert post(app).status_code == 507

    app.test_client().post(f"/delete/{'d' * 64}")

    assert post(app).status_code == 200


def test_zero_means_no_limit(make_app):
    app = make_app(0)

    assert [post(app).status_code for _ in range(3)] == [200, 200, 200]
    assert stored(app) == 3
