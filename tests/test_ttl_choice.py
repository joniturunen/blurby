"""The creator chooses how long a secret is kept (#18), up to the server's cap."""

from datetime import datetime, timedelta

import pytest
from html_helpers import elements

from blurby import create_app
from blurby.cleanup import delete_expired
from blurby.config import load_config, ttl_choices
from blurby.models import Data, db
from blurby.views import describe_hours

ORIGIN = {"Origin": "http://x"}

# Configuration


@pytest.mark.parametrize(
    ("environ", "cap"),
    [
        ({}, 48),
        ({"BLURBY_TTL_HOURS": "1"}, 1),
        ({"BLURBY_MAX_TTL_HOURS": "336"}, 336),
        # A cap below the default TTL is raised to it.
        ({"BLURBY_TTL_HOURS": "48", "BLURBY_MAX_TTL_HOURS": "24"}, 48),
    ],
)
def test_the_cap_defaults_to_the_default_ttl(environ, cap):
    # An upgrade never lets users keep secrets longer than before: longer TTLs
    # need the admin to raise BLURBY_MAX_TTL_HOURS.
    assert load_config(environ)["BLURBY_MAX_TTL_HOURS"] == cap


@pytest.mark.parametrize(
    ("ttl", "cap", "choices"),
    [
        (48, 48, [1, 24, 48]),
        (48, 336, [1, 24, 48, 120, 168, 336]),
        (72, 72, [1, 24, 48, 72]),
        (1, 1, [1]),
        (48, 200, [1, 24, 48, 120, 168]),
    ],
)
def test_the_choices_are_the_presets_up_to_the_cap_plus_the_default(ttl, cap, choices):
    app = create_app({"BLURBY_TTL_HOURS": ttl, "BLURBY_MAX_TTL_HOURS": cap})

    with app.app_context():
        assert ttl_choices() == choices


@pytest.mark.parametrize(
    ("hours", "label"),
    [
        (1, "1 hour"),
        (36, "36 hours"),
        (24, "1 day"),
        (120, "5 days"),
        (168, "1 week"),
        (336, "2 weeks"),
    ],
)
def test_ttls_are_described_in_words(hours, label):
    assert describe_hours(hours) == label


# The form


@pytest.fixture
def capped_app(app):
    app.config["BLURBY_MAX_TTL_HOURS"] = 336
    return app


def test_the_form_offers_the_choices_with_the_default_selected(capped_app):
    body = capped_app.test_client().get("/").get_data(as_text=True)

    options = elements(body, "option")
    assert [option["value"] for option in options] == [
        "1",
        "24",
        "48",
        "120",
        "168",
        "336",
    ]
    assert [option["value"] for option in options if "selected" in option] == ["48"]
    assert elements(body, "select", name="ttl_hours")


def post(app, **form):
    return app.test_client().post("/", data={"data": "secret", **form}, headers=ORIGIN)


def test_a_chosen_ttl_sets_the_secrets_expiry(capped_app):
    response = post(capped_app, ttl_hours="120")

    assert response.status_code == 200
    secret = Data.query.one()
    assert secret.expires_at == secret.timestamp + timedelta(hours=120)


def test_without_a_choice_the_default_ttl_applies(capped_app):
    # curl and scripts post only the secret.
    post(capped_app)

    secret = Data.query.one()
    assert secret.expires_at == secret.timestamp + timedelta(hours=48)


@pytest.mark.parametrize("ttl_hours", ["337", "2", "abc", "", "-1"])
def test_a_ttl_that_is_not_offered_is_rejected_with_400(capped_app, ttl_hours):
    response = post(capped_app, ttl_hours=ttl_hours)

    assert response.status_code == 400
    assert "Invalid TTL" in response.get_data(as_text=True)
    assert Data.query.count() == 0


def test_a_ttl_over_the_cap_is_rejected(app):
    # The default cap is the default TTL: 2 weeks isn't offered.
    response = post(app, ttl_hours="336")

    assert response.status_code == 400
    assert Data.query.count() == 0


def test_the_link_page_says_when_the_secret_is_deleted(capped_app):
    body = post(capped_app, ttl_hours="1").get_data(as_text=True)

    expires = Data.query.one().expires_at
    [when] = elements(body, "time")
    assert when["datetime"] == expires.astimezone().isoformat(timespec="minutes")


# Reading and cleanup


def add_secret(link, age, ttl=None):
    created = datetime.now() - age
    db.session.add(
        Data(
            sha_link=link,
            data=f"secret {link}",
            creator="anonymous",
            timestamp=created,
            expires_at=created + ttl if ttl else None,
        )
    )
    db.session.commit()


def test_a_secret_is_shown_until_its_own_expiry(app):
    # Older than the default TTL (48 h), but kept for a week.
    add_secret("w" * 64, timedelta(hours=50), ttl=timedelta(days=7))
    # Younger than the default TTL, but kept for an hour only.
    add_secret("h" * 64, timedelta(hours=2), ttl=timedelta(hours=1))

    client = app.test_client()
    assert client.get("/link/" + "w" * 64).status_code == 200
    assert client.get("/link/" + "h" * 64).status_code == 404


def test_cleanup_deletes_secrets_past_their_own_expiry(app):
    add_secret("kept-for-a-week", timedelta(hours=50), ttl=timedelta(days=7))
    add_secret("kept-for-an-hour", timedelta(hours=2), ttl=timedelta(hours=1))
    # Written before 0.4.0: no expiry of its own, so the default TTL applies.
    add_secret("old-and-expired", timedelta(hours=49))
    add_secret("old-and-fresh", timedelta(hours=47))

    assert delete_expired() == 2
    assert sorted(data.sha_link for data in Data.query.all()) == [
        "kept-for-a-week",
        "old-and-fresh",
    ]


def test_about_shows_the_default_and_the_longest_ttl(capped_app):
    body = capped_app.test_client().get("/about").get_data(as_text=True)

    assert "2 days" in body
    assert "2 weeks" in body
