from blurby.main import create_app, db


def setup_database():
    try:
        with create_app().app_context():
            db.create_all()
        print("Database created!")
    except:
        print(
            f"Can't create database, maybe it already exists or path is not writable?"
        )


if __name__ == "__main__":
    setup_database()
