import pytest

from blurby import create_app
from blurby.config import load_config


def test_defaults_match_the_docker_deployment():
    config = load_config({})

    assert config["BLURBY_DB_FILE"] == "/blurby/data/sqlite.db"
    assert config["SQLALCHEMY_DATABASE_URI"] == "sqlite:////blurby/data/sqlite.db"
    assert config["BLURBY_TTL_HOURS"] == 48
    assert config["BLURBY_THREADS"] == 8
    assert config["BLURBY_HOST_IP"] == "0.0.0.0"
    assert config["BLURBY_CLEANUP_INTERVAL"] == 60


def test_environment_variables_override_the_defaults():
    config = load_config(
        {
            "BLURBY_DB_FILE": "/tmp/blurby.db",
            "BLURBY_TTL_HOURS": "1",
            "BLURBY_THREADS": "2",
            "BLURBY_HOST_IP": "127.0.0.1",
            "BLURBY_CLEANUP_INTERVAL": "5",
        }
    )

    assert config["BLURBY_DB_FILE"] == "/tmp/blurby.db"
    assert config["SQLALCHEMY_DATABASE_URI"] == "sqlite:////tmp/blurby.db"
    assert config["BLURBY_TTL_HOURS"] == 1
    assert config["BLURBY_THREADS"] == 2
    assert config["BLURBY_HOST_IP"] == "127.0.0.1"
    assert config["BLURBY_CLEANUP_INTERVAL"] == 5


def test_non_numeric_ttl_is_rejected():
    with pytest.raises(ValueError):
        load_config({"BLURBY_TTL_HOURS": "two days"})


def test_create_app_reads_the_environment(monkeypatch):
    monkeypatch.setenv("BLURBY_TTL_HOURS", "12")

    app = create_app()

    assert app.config["BLURBY_TTL_HOURS"] == 12


def test_create_app_test_config_overrides_the_environment(monkeypatch):
    monkeypatch.setenv("BLURBY_TTL_HOURS", "12")

    app = create_app({"BLURBY_TTL_HOURS": 3})

    assert app.config["BLURBY_TTL_HOURS"] == 3
