import pytest

from blurby import create_app
from blurby.models import db


@pytest.fixture
def app():
    """An app with an empty in-memory database, inside an app context."""
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture
def make_file_app():
    """Factory for apps backed by an on-disk SQLite file; disposes their engines."""
    apps = []

    def make(db_file):
        app = create_app(
            {
                "TESTING": True,
                "BLURBY_DB_FILE": str(db_file),
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file}",
            }
        )
        apps.append(app)
        return app

    yield make
    for app in apps:
        with app.app_context():
            db.engine.dispose()
