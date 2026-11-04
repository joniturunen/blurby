"""The user's name comes from a request header that an auth proxy sets:
`username` by default, the one BLURBY_USERNAME_HEADER names, or none at all."""

import pytest

from blurby import create_app
from blurby.config import load_config
from blurby.models import Data, db

LINK = "a" * 64


@pytest.fixture
def make_app():
    apps = []

    def make(header):
        app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "BLURBY_USERNAME_HEADER": header,
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


def create(app, **headers):
    app.test_client().post("/", data={"data": "secret"}, headers=headers)
    with app.app_context():
        return db.session.query(Data).one().creator


def burn(app, **headers):
    with app.app_context():
        db.session.add(Data(sha_link=LINK, data="secret", creator="anonymous"))
        db.session.commit()
    app.test_client().post(f"/burn/{LINK}", headers=headers)
    with app.app_context():
        return db.session.get(Data, LINK).burnt_by


@pytest.mark.parametrize(
    ("environ", "header"),
    [
        ({}, "username"),
        ({"BLURBY_USERNAME_HEADER": "X-Forwarded-User"}, "X-Forwarded-User"),
        ({"BLURBY_USERNAME_HEADER": " Remote-User "}, "Remote-User"),
        ({"BLURBY_USERNAME_HEADER": ""}, ""),
        ({"BLURBY_USERNAME_HEADER": "  "}, ""),
    ],
)
def test_the_setting_names_the_header(environ, header):
    assert load_config(environ)["BLURBY_USERNAME_HEADER"] == header


def test_by_default_the_username_header_names_the_user(make_app):
    app = make_app("username")

    page = app.test_client().get("/", headers={"username": "alice"})

    assert "🤫 alice" in page.get_data(as_text=True)
    assert create(app, username="alice") == "alice"


def test_another_header_names_the_user_and_username_is_ignored(make_app):
    app = make_app("X-Forwarded-User")
    headers = {"X-Forwarded-User": "alice", "username": "mallory"}

    page = app.test_client().get("/", headers=headers).get_data(as_text=True)

    assert "🤫 alice" in page
    assert "mallory" not in page
    assert create(app, **headers) == "alice"


def test_the_header_name_is_not_case_sensitive(make_app):
    app = make_app("X-Forwarded-User")

    assert create(app, **{"x-forwarded-user": "alice"}) == "alice"


def test_burning_names_the_reader_from_the_same_header(make_app):
    app = make_app("Remote-User")

    assert burn(app, **{"Remote-User": "bob", "username": "mallory"}) == "bob"


def test_without_a_header_everyone_is_anonymous(make_app):
    app = make_app("")

    page = app.test_client().get("/", headers={"username": "mallory"})

    assert "🤫 anonymous" in page.get_data(as_text=True)
    assert create(app, username="mallory") == "anonymous"


def test_without_a_header_a_burn_names_no_one(make_app):
    app = make_app("")

    assert burn(app, username="mallory") is None


def test_a_missing_header_means_anonymous(make_app):
    app = make_app("X-Forwarded-User")

    assert create(app) == "anonymous"
